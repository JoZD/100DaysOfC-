from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Effort(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Risk(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Finding(BaseModel):
    tenant_id: str
    resource_id: str
    rule_id: str
    category: str
    monthly_savings_usd: float
    remediation_effort: Effort
    risk: Risk
    remediation_action: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
