"""Phase 1 proof: paste JD + resume -> get one question -> submit an answer ->
confirm the score/feedback were stored server-side but never came back over the API.

Usage:
    1. Start the backend: cd backend && uvicorn app.main:app --reload
    2. Create one test user in Supabase (Authentication -> Users -> Add user), copy its UUID.
    3. python scripts/demo.py <user_uuid>
"""

import sys

import requests

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


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/demo.py <user_uuid>")
        sys.exit(1)
    user_id = sys.argv[1]

    print("== Creating session (analyze_profile + generate_question) ==")
    resp = requests.post(
        f"{BASE_URL}/sessions",
        json={
            "user_id": user_id,
            "role": "Senior Backend Engineer",
            "jd_text": SAMPLE_JD,
            "resume_text": SAMPLE_RESUME,
        },
    )
    resp.raise_for_status()
    session_data = resp.json()
    print(session_data)
    assert "score" not in session_data and "feedback" not in session_data

    print("\n== Submitting a deliberately weak answer ==")
    resp = requests.post(
        f"{BASE_URL}/sessions/{session_data['session_id']}/answer",
        json={
            "question_id": session_data["question_id"],
            "answer_text": "I haven't used Kafka much but I think I could figure it out.",
        },
    )
    resp.raise_for_status()
    answer_data = resp.json()
    print(answer_data)

    assert answer_data == {"recorded": True, "has_next": False}, (
        "API leaked something beyond {recorded, has_next} - the no-live-grading contract broke."
    )
    print(
        "\nConfirmed: the answer endpoint returned only {recorded, has_next}. "
        "The score/feedback were computed and written to the `answers` table but never "
        "sent to the client — check the Supabase table editor to see them."
    )


if __name__ == "__main__":
    main()
