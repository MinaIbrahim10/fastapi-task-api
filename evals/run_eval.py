import json
from datetime import datetime, timezone
from pathlib import Path

from src.llm.client import TriageOutputError, call_triage_model


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals" / "cases.json"
RESULTS_PATH = ROOT / "evals" / "latest-results.json"


def main():
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    results = []
    category_hits = 0
    team_hits = 0
    exact_hits = 0
    trusted = 0

    print(f"Running {len(cases)} labelled eval cases...\n")

    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case['id']}")

        try:
            output = call_triage_model(case["text"])
            trusted += 1

            actual_category = output.category.value
            actual_team = output.suggested_team.value

            category_ok = actual_category == case["expected_category"]
            team_ok = actual_team == case["expected_team"]
            exact_ok = category_ok and team_ok

            category_hits += int(category_ok)
            team_hits += int(team_ok)
            exact_hits += int(exact_ok)

            print(
                f"  category: {actual_category} "
                f"(expected {case['expected_category']}) "
                f"{'PASS' if category_ok else 'FAIL'}"
            )

            print(
                f"  team:     {actual_team} "
                f"(expected {case['expected_team']}) "
                f"{'PASS' if team_ok else 'FAIL'}"
            )

            results.append(
                {
                    "id": case["id"],
                    "input": case["text"],
                    "expected_category": case["expected_category"],
                    "actual_category": actual_category,
                    "expected_team": case["expected_team"],
                    "actual_team": actual_team,
                    "category_match": category_ok,
                    "team_match": team_ok,
                    "exact_match": exact_ok,
                    "trusted_response": True,
                    "output": output.model_dump(mode="json"),
                }
            )

        except TriageOutputError as exc:
            print("  SAFE FAILURE:", exc)

            results.append(
                {
                    "id": case["id"],
                    "input": case["text"],
                    "expected_category": case["expected_category"],
                    "expected_team": case["expected_team"],
                    "trusted_response": False,
                    "error": str(exc),
                }
            )

        print()

    total = len(cases)

    summary = {
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "prompt_version": "v1",
        "total_cases": total,
        "trusted_responses": trusted,
        "category_matches": category_hits,
        "team_matches": team_hits,
        "exact_matches": exact_hits,
        "category_accuracy": category_hits / total,
        "team_accuracy": team_hits / total,
        "exact_accuracy": exact_hits / total,
    }

    RESULTS_PATH.write_text(
        json.dumps(
            {
                "summary": summary,
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print("=" * 60)
    print("EVAL SUMMARY")
    print("=" * 60)
    print(f"Trusted responses : {trusted}/{total}")
    print(f"Category accuracy : {category_hits}/{total} = {category_hits/total:.1%}")
    print(f"Team accuracy     : {team_hits}/{total} = {team_hits/total:.1%}")
    print(f"Exact accuracy    : {exact_hits}/{total} = {exact_hits/total:.1%}")
    print(f"Results saved     : {RESULTS_PATH}")


if __name__ == "__main__":
    main()
