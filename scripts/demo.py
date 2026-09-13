"""End-to-end proof of the Phase 3 pipeline: paste JD + resume -> LangGraph runs
analyze_profile -> generate_question, then loops evaluate_answer -> route_after_eval
(follow up / next question / end) until the interview completes — while confirming the
API never returns a score or feedback at any point along the way.

Usage:
    1. Start the backend: cd backend && uvicorn app.main:app --reload
    2. Create a confirmed Supabase user (Authentication -> Users -> Add user, with a password),
       or sign up through the frontend.
    3. python scripts/demo.py <email> <password>
"""

import sys

import requests
from supabase import create_client

BASE_URL = "http://localhost:8000"

SAMPLE_JD = """
Senior Backend Engineer - we need someone with 4+ years building production APIs in Python,
strong experience with distributed systems and message queues (Kafka preferred), and a track
record of owning services end-to-end in a cloud environment (AWS or GCP).
"""

SAMPLE_RESUME = """
Backend engineer with 5 years of experience building REST APIs in Python (FastAPI, Django).
Deployed and maintained services on AWS (EC2, RDS, Lambda). Led migration of a monolith to
microservices. No direct experience with Kafka or other message queues, but familiar with
basic pub/sub concepts from academic projects.
"""

# Deliberately weak so the evaluator is likely to trigger follow-ups — exercises more of the
# route_after_eval branching than a uniformly strong or uniformly weak run would.
SAMPLE_ANSWERS = [
    "I haven't used Kafka much but I think I could figure it out.",
    "Not really, no direct experience with that either.",
    "We used AWS Lambda a bit, I don't remember the specifics.",
    "I mostly just followed the runbook someone else wrote.",
    "Not sure, I'd have to look that up.",
]


def get_access_token(email: str, password: str) -> str:
    # Uses the same Supabase project as the backend/frontend .env files — only the URL and
    # anon key are needed here since signing in doesn't require elevated privileges.
    settings_env = _read_env("frontend/.env") or _read_env("backend/.env")
    url = settings_env.get("VITE_SUPABASE_URL") or settings_env.get("SUPABASE_URL")
    anon_key = settings_env.get("VITE_SUPABASE_ANON_KEY")
    if not url or not anon_key:
        raise SystemExit(
            "Couldn't find VITE_SUPABASE_URL/VITE_SUPABASE_ANON_KEY in frontend/.env. "
            "Run this script from the repo root, or set them as env vars."
        )
    client = create_client(url, anon_key)
    result = client.auth.sign_in_with_password({"email": email, "password": password})
    return result.session.access_token


def _read_env(path: str) -> dict:
    try:
        with open(path) as f:
            lines = f.readlines()
    except FileNotFoundError:
        return {}
    env = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def assert_no_leak(body: dict) -> None:
    leaked = {"score", "feedback", "needs_followup"} & body.keys()
    assert not leaked, f"API leaked internal fields to the client: {leaked}"


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python scripts/demo.py <email> <password>")
        sys.exit(1)
    email, password = sys.argv[1], sys.argv[2]

    token = get_access_token(email, password)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print("== Creating session (analyze_profile -> generate_question, via the start graph) ==")
    resp = requests.post(
        f"{BASE_URL}/sessions",
        headers=headers,
        json={"role": "Senior Backend Engineer", "jd_text": SAMPLE_JD, "resume_text": SAMPLE_RESUME},
    )
    resp.raise_for_status()
    session_data = resp.json()
    assert_no_leak(session_data)
    session_id = session_data["session_id"]
    question_id = session_data["question_id"]
    question_text = session_data["question_text"]

    turn = 0
    while True:
        turn += 1
        print(f"\n-- Turn {turn} --")
        print("Q:", question_text)
        answer = SAMPLE_ANSWERS[(turn - 1) % len(SAMPLE_ANSWERS)]
        print("A:", answer)

        resp = requests.post(
            f"{BASE_URL}/sessions/{session_id}/answer",
            headers=headers,
            json={"question_id": question_id, "answer_text": answer},
        )
        resp.raise_for_status()
        answer_data = resp.json()
        assert_no_leak(answer_data)
        assert set(answer_data.keys()) == {"recorded", "has_next"}, (
            f"Unexpected shape from /answer: {answer_data}"
        )
        print("-> answer response:", answer_data, "(no score/feedback, as designed)")

        if not answer_data["has_next"]:
            print("\nInterview complete — route_after_eval decided to end the session.")
            break

        resp = requests.get(f"{BASE_URL}/sessions/{session_id}/next-question", headers=headers)
        resp.raise_for_status()
        next_q = resp.json()
        question_id = next_q["question_id"]
        question_text = next_q["question_text"]
        if next_q["is_followup"]:
            print("(this is a follow-up — route_after_eval judged the last answer too weak)")

    print(
        f"\nRan {turn} turns end-to-end. Every /answer response contained only "
        "{recorded, has_next} — scores/feedback were computed and stored in the `answers` "
        "table but never sent to the client. Check the Supabase table editor to see them, "
        "including the follow-up chains via questions.parent_question_id."
    )


if __name__ == "__main__":
    main()
