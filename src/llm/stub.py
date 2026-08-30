from .schema import TriageResponse


def get_stub_triage() -> TriageResponse:
    return TriageResponse(
        category="bug",
        urgency="normal",
        suggested_team="engineering",
        confidence=0.95,
        needs_review=False,
        reason="Stub response used for deterministic development and testing.",
    )
