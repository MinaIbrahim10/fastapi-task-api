import json

from src.llm.client import _parse_and_validate
from src.llm.schema import (
    Category,
    SuggestedTeam,
    expected_team_for_category,
)


def test_category_team_map_is_complete():
    expected = {
        Category.BUG: SuggestedTeam.ENGINEERING,
        Category.FEATURE: SuggestedTeam.PRODUCT,
        Category.ACCOUNT: SuggestedTeam.SUPPORT,
        Category.BILLING: SuggestedTeam.BILLING,
        Category.SECURITY: SuggestedTeam.SECURITY,
        Category.OTHER: SuggestedTeam.SUPPORT,
    }

    for category, team in expected.items():
        assert expected_team_for_category(category) == team


def test_backend_corrects_wrong_security_team():
    raw = json.dumps(
        {
            "category": "security",
            "urgency": "high",
            "suggested_team": "engineering",
            "confidence": 0.95,
            "needs_review": False,
            "reason": "Unauthorized privilege escalation.",
        }
    )

    result = _parse_and_validate(raw)

    assert result.category == "security"
    assert result.suggested_team == "security"


def test_backend_corrects_wrong_feature_team():
    raw = json.dumps(
        {
            "category": "feature",
            "urgency": "low",
            "suggested_team": "support",
            "confidence": 0.9,
            "needs_review": False,
            "reason": "The user requested a new feature.",
        }
    )

    result = _parse_and_validate(raw)

    assert result.category == "feature"
    assert result.suggested_team == "product"


def test_correct_team_is_preserved():
    raw = json.dumps(
        {
            "category": "billing",
            "urgency": "normal",
            "suggested_team": "billing",
            "confidence": 0.9,
            "needs_review": False,
            "reason": "The user reports a billing problem.",
        }
    )

    result = _parse_and_validate(raw)

    assert result.category == "billing"
    assert result.suggested_team == "billing"
