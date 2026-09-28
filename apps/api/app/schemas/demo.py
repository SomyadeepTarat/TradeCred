from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class SimulatorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    amount_minor: StrictInt = Field(gt=0, le=2**53 - 1)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    reference: str = Field(pattern=r"^[A-Za-z0-9_./-]{1,160}$")
    mode: Literal["valid", "invalid"]


class SimulatorResult(BaseModel):
    id: UUID
    uncertain: bool = False
    accepted: bool
    code: str
    event_id: str
    asset_id: str
    transaction_id: str | None = None
    backend: str | None = None


class SimulatorAsset(BaseModel):
    asset_id: str
    currency: str
    status: str


class SecurityView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    event_type: str
    reason: str
    request_id: str
    created_at: datetime
