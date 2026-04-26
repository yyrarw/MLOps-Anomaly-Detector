from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BalanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: float = Field(gt=0)


class BalanceResponse(BaseModel):
    balance: float


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: float
    type: str
    task_id: int | None
    created_at: datetime
