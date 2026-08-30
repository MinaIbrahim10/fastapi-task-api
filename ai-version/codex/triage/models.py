from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Category(str, Enum):
    bug = "bug"
    feature = "feature"
    account = "account"
    billing = "billing"
    security = "security"
    other = "other"


class Urgency(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    critical = "critical"


class Team(str, Enum):
    engineering = "engineering"
    product = "product"
    support = "support"
    billing = "billing"
    security = "security"


class TriageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=2000)


class TriageResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    category: Category
    urgency: Urgency
    suggested_team: Team
    confidence: float = Field(ge=0.0, le=1.0)
    needs_review: bool
    reason: str = Field(min_length=1, max_length=180)

    @field_validator("reason")
    @classmethod
    def one_short_sentence(cls, value: str) -> str:
        value = value.strip()
        if "\n" in value or len(value.split()) > 30:
            raise ValueError("reason must be one short sentence")
        return value
