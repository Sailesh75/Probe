"""Phase 5 eval: run every sample answer in sample_answers.jsonl through the real evaluator
and compare its score against a human (mine) judgment call, recorded in advance in the
`expected_score`/`rationale` fields — so this is a genuine agreement check, not a check
written to match whatever the model happens to output.

Writes each result to results/evaluator_results.jsonl as it goes (not just at the end), so a
Gemini quota failure partway through still leaves whatever was completed on disk instead of
losing the whole run.

Usage: python eval/run_evaluator_eval.py   (run from the repo root)
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from google.genai import errors  # noqa: E402

from app.prompts.evaluator import evaluate_answer  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
INPUT_PATH = EVAL_DIR / "sample_answers.jsonl"
OUTPUT_PATH = EVAL_DIR / "results" / "evaluator_results.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    samples = load_jsonl(INPUT_PATH)
    OUTPUT_PATH.parent.mkdir(exist_ok=True)

    results = []
    with open(OUTPUT_PATH, "w") as out_f:
        for i, sample in enumerate(samples, start=1):
            print(f"[{i}/{len(samples)}] {sample['id']}...", end=" ", flush=True)
            try:
                eval_result = evaluate_answer(
                    question_text=sample["question_text"],
                    target_area=sample["target_area"],
                    answer_text=sample["answer_text"],
                )
            except errors.APIError as exc:
                print(f"STOPPED — Gemini API error: {exc}")
                print(
                    f"\n{i - 1}/{len(samples)} items completed before this failure. "
                    "Results so far are saved; re-run later to pick up more (this script "
                    "doesn't currently skip already-done items, so it restarts from the top)."
                )
                break

            row = {
                "id": sample["id"],
                "expected_score": sample["expected_score"],
                "actual_score": eval_result.score,
                "exact_match": eval_result.score == sample["expected_score"],
                "within_one": abs(eval_result.score - sample["expected_score"]) <= 1,
                "actual_feedback": eval_result.feedback,
                "actual_needs_followup": eval_result.needs_followup,
                "rationale": sample["rationale"],
            }
            results.append(row)
            out_f.write(json.dumps(row) + "\n")
            out_f.flush()
            print(f"expected={sample['expected_score']} actual={eval_result.score}")

    if not results:
        print("No results to summarize.")
        return

    exact = sum(r["exact_match"] for r in results)
    within_one = sum(r["within_one"] for r in results)
    mae = sum(abs(r["actual_score"] - r["expected_score"]) for r in results) / len(results)

    print("\n=== Summary ===")
    print(f"Items evaluated: {len(results)}/{len(samples)}")
    print(f"Exact agreement: {exact}/{len(results)} ({exact / len(results):.0%})")
    print(f"Within-1 agreement: {within_one}/{len(results)} ({within_one / len(results):.0%})")
    print(f"Mean absolute error: {mae:.2f}")

    print("\n=== Disagreements (>1 point off) ===")
    for r in results:
        if not r["within_one"]:
            print(f"- {r['id']}: expected {r['expected_score']}, got {r['actual_score']}")
            print(f"  model feedback: {r['actual_feedback']}")


if __name__ == "__main__":
    main()
