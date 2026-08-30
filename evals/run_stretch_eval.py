import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from src.llm.client import (
    LLMUnavailableError,
    TriageOutputError,
    call_triage_model,
)


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals" / "stretch-25-cases.json"
RESULTS_PATH = ROOT / "evals" / "stretch-v2-results.json"


def percentage(hits: int, total: int) -> float:
    if total == 0:
        return 0.0
    return hits / total


def main():
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    results = []

    trusted = 0
    category_hits = 0
    team_hits = 0
    exact_hits = 0

    groups = defaultdict(
        lambda: {
            "total": 0,
            "trusted": 0,
            "exact": 0,
        }
    )

    print(f"Running {len(cases)} stretch eval cases...\n")

    for index, case in enumerate(cases, start=1):
        difficulty = case["difficulty"]
        attack = case["attack"]

        groups[difficulty]["total"] += 1

        if attack:
            groups["attacks"]["total"] += 1

        print(
            f"[{index:02d}/{len(cases)}] "
            f"{case['id']} "
            f"[{difficulty}]"
            f"{' [ATTACK]' if attack else ''}"
        )

        try:
            output = call_triage_model(case["text"])

            trusted += 1
            groups[difficulty]["trusted"] += 1

            if attack:
                groups["attacks"]["trusted"] += 1

            actual_category = output.category.value
            actual_team = output.suggested_team.value

            category_ok = (
                actual_category == case["expected_category"]
            )
            team_ok = (
                actual_team == case["expected_team"]
            )
            exact_ok = category_ok and team_ok

            category_hits += int(category_ok)
            team_hits += int(team_ok)
            exact_hits += int(exact_ok)

            if exact_ok:
                groups[difficulty]["exact"] += 1

                if attack:
                    groups["attacks"]["exact"] += 1

            print(
                "  expected:",
                case["expected_category"],
                "/",
                case["expected_team"],
            )

            print(
                "  actual  :",
                actual_category,
                "/",
                actual_team,
            )

            print(
                "  result  :",
                "PASS" if exact_ok else "FAIL",
            )

            results.append(
                {
                    **case,
                    "actual_category": actual_category,
                    "actual_team": actual_team,
                    "category_match": category_ok,
                    "team_match": team_ok,
                    "exact_match": exact_ok,
                    "trusted_response": True,
                    "output": output.model_dump(mode="json"),
                }
            )

        except (TriageOutputError, LLMUnavailableError) as exc:
            print("  result  : SAFE FAILURE")
            print("  error   :", str(exc))

            results.append(
                {
                    **case,
                    "exact_match": False,
                    "trusted_response": False,
                    "error": str(exc),
                }
            )

        print()

    total = len(cases)

    summary = {
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "prompt_version": os.getenv(
            "LLM_PROMPT_VERSION",
            "v1",
        ),
        "total_cases": total,
        "trusted_responses": trusted,
        "category_matches": category_hits,
        "team_matches": team_hits,
        "exact_matches": exact_hits,
        "category_accuracy": percentage(
            category_hits,
            total,
        ),
        "team_accuracy": percentage(
            team_hits,
            total,
        ),
        "exact_accuracy": percentage(
            exact_hits,
            total,
        ),
        "groups": {},
    }

    for name in ("easy", "hard", "attacks"):
        data = groups[name]

        summary["groups"][name] = {
            **data,
            "exact_accuracy": percentage(
                data["exact"],
                data["total"],
            ),
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

    print("=" * 68)
    print("STRETCH EVAL SUMMARY")
    print("=" * 68)

    print(
        f"Trusted responses : "
        f"{trusted}/{total}"
    )

    print(
        f"Category accuracy : "
        f"{category_hits}/{total} "
        f"= {percentage(category_hits, total):.1%}"
    )

    print(
        f"Team accuracy     : "
        f"{team_hits}/{total} "
        f"= {percentage(team_hits, total):.1%}"
    )

    print(
        f"Exact accuracy    : "
        f"{exact_hits}/{total} "
        f"= {percentage(exact_hits, total):.1%}"
    )

    print()

    for name in ("easy", "hard", "attacks"):
        data = summary["groups"][name]

        print(
            f"{name.capitalize():8s}: "
            f"{data['exact']}/{data['total']} "
            f"= {data['exact_accuracy']:.1%}"
        )

    print()
    print("Results:", RESULTS_PATH)


if __name__ == "__main__":
    main()
