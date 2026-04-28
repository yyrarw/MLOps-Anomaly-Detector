from datetime import datetime
from typing import Any, List

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PredictionRowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    metric: str = Field(min_length=1, max_length=255)
    value: float
    node: str = Field(min_length=1, max_length=255)

    @field_validator("metric", "node")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field must not be empty")
        return normalized


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: int = Field(gt=0)
    rows: List[PredictionRowRequest] = Field(min_length=1)


class PredictResponse(BaseModel):
    task_id: int
    status: str
    balance: float


class PredictionHistoryResponse(BaseModel):
    task_id: int
    model_id: int
    status: str
    credits_charged: float
    created_at: datetime
