from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Category(StrEnum):
    BUG = "bug"
    FEATURE = "feature"
    ACCOUNT = "account"
    BILLING = "billing"
    SECURITY = "security"
    OTHER = "other"


class Urgency(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class SuggestedTeam(StrEnum):
    ENGINEERING = "engineering"
    PRODUCT = "product"
    SUPPORT = "support"
    BILLING = "billing"
    SECURITY = "security"


class TriageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Software or product support message to classify.",
    )


class TriageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category
    urgency: Urgency
    suggested_team: SuggestedTeam
    confidence: float = Field(..., ge=0.0, le=1.0)
    needs_review: bool
    reason: str = Field(..., min_length=1, max_length=240)
