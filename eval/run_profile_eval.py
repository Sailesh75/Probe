"""Phase 5 spot-check: run analyze_profile on a few real-shaped JD/resume pairs and print the
structured output next to a written expectation, for manual review — does it flag the gaps a
real interviewer would actually probe, without inventing gaps that aren't there?

This one is qualitative (the plan's own framing: "does it correctly flag gaps you'd actually
expect an interviewer to probe?"), so it prints for a human to judge rather than asserting
pass/fail. Results are still saved to results/profile_results.jsonl for the eval writeup.

Usage: python eval/run_profile_eval.py   (run from the repo root)
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from google.genai import errors  # noqa: E402

from app.prompts.profile_analyzer import analyze_profile  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
INPUT_PATH = EVAL_DIR / "sample_profiles.jsonl"
OUTPUT_PATH = EVAL_DIR / "results" / "profile_results.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    samples = load_jsonl(INPUT_PATH)
    OUTPUT_PATH.parent.mkdir(exist_ok=True)

    with open(OUTPUT_PATH, "w") as out_f:
        for i, sample in enumerate(samples, start=1):
            print(f"\n{'=' * 70}\n[{i}/{len(samples)}] {sample['id']}")
            print(f"Expectation: {sample['expectation']}")
            try:
                result = analyze_profile(sample["jd_text"], sample["resume_text"])
            except errors.APIError as exc:
                print(f"STOPPED — Gemini API error: {exc}")
                break

            print(f"\ngap_areas:      {result.gap_areas}")
            print(f"strength_areas: {result.strength_areas}")
            print(f"jd_requirements: {result.jd_requirements}")
            print(f"resume_highlights: {result.resume_highlights}")

            row = {"id": sample["id"], "expectation": sample["expectation"], **result.model_dump()}
            out_f.write(json.dumps(row) + "\n")
            out_f.flush()

    print(f"\n{'=' * 70}\nSaved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
