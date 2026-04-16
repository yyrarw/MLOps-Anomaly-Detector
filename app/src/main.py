import hashlib
import os
import secrets
from datetime import datetime
from typing import Any, List

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from src.database import get_db
from src.init_db import init_db
from src.models import MLModelORM, PredictionResultORM, TaskORM, TransactionORM, UserORM

app = FastAPI(title="MLOps Anomaly Detector")
security = HTTPBasic()

SUPPORTED_METRICS = tuple(
    metric.strip()
    for metric in os.getenv(
        "SUPPORTED_METRICS",
        "gpu_utilization,memory_usage,latency_ms,queue_size,tokens_per_second",
    ).split(",")
    if metric.strip()
)


@app.on_event("startup")
def on_startup():
    init_db()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _error_payload(code: str, message: str, details: Any = None) -> dict[str, Any]:
    payload = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return payload


def _http_error_code(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        402: "insufficient_balance",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
    }.get(status_code, "request_error")


def _get_current_user(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> UserORM:
    user = db.query(UserORM).filter(UserORM.email == credentials.username).first()
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Basic"},
    )

    if user is None:
        raise invalid_credentials

    hashed_password = _hash_password(credentials.password)
    if not secrets.compare_digest(user.hashed_password, hashed_password):
        raise invalid_credentials

    return user


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, str):
        message = detail
        details = None
    elif isinstance(detail, dict):
        message = str(detail.get("message", "Request failed"))
        details = {key: value for key, value in detail.items() if key != "message"} or None
    else:
        message = "Request failed"
        details = detail
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(_http_error_code(exc.status_code), message, details),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_payload("validation_error", "Validation failed", exc.errors()),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_payload("internal_server_error", "Internal server error"),
    )


class ErrorResponse(BaseModel):
    error: dict[str, Any]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email:
            raise ValueError("Email must contain '@'")
        local_part, _, domain = email.partition("@")
        if not local_part or "." not in domain:
            raise ValueError("Email format is invalid")
        return email


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str
    balance: float
    created_at: datetime


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


class MLModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    cost_per_request: float


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


class PredictionResponse(BaseModel):
    task_id: int
    status: str
    credits_charged: float
    balance: float
    valid_rows_count: int
    invalid_rows: list[dict[str, Any]]
    anomalies: list[dict[str, Any]]
    created_at: datetime


class PredictionHistoryResponse(BaseModel):
    task_id: int
    model_id: int
    status: str
    credits_charged: float
    created_at: datetime


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def register_user(data: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(UserORM).filter(UserORM.email == data.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = UserORM(
        email=data.email,
        hashed_password=_hash_password(data.password),
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post(
    "/auth/login",
    response_model=UserResponse,
    responses={401: {"model": ErrorResponse}},
)
def login(current_user: UserORM = Depends(_get_current_user)):
    return current_user


@app.get(
    "/users/me",
    response_model=UserResponse,
    responses={401: {"model": ErrorResponse}},
)
def get_current_user_profile(current_user: UserORM = Depends(_get_current_user)):
    return current_user


@app.get(
    "/balance",
    response_model=BalanceResponse,
    responses={401: {"model": ErrorResponse}},
)
def get_balance(current_user: UserORM = Depends(_get_current_user)):
    return BalanceResponse(balance=current_user.balance)


@app.post(
    "/balance/top-up",
    response_model=BalanceResponse,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def top_up_balance(
    data: BalanceRequest,
    current_user: UserORM = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    current_user.balance += data.amount
    db.add(TransactionORM(user_id=current_user.id, amount=data.amount, type="topup"))
    db.commit()
    db.refresh(current_user)
    return BalanceResponse(balance=current_user.balance)


@app.get("/models", response_model=List[MLModelResponse])
def list_models(db: Session = Depends(get_db)):
    return db.query(MLModelORM).all()


@app.post(
    "/predict",
    response_model=PredictionResponse,
    responses={
        401: {"model": ErrorResponse},
        402: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def predict(
    data: PredictRequest,
    current_user: UserORM = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    model = db.get(MLModelORM, data.model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    unsupported_metrics = sorted({row.metric for row in data.rows if row.metric not in SUPPORTED_METRICS})
    if unsupported_metrics:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Unsupported metrics in request",
                "supported_metrics": list(SUPPORTED_METRICS),
                "invalid_metrics": unsupported_metrics,
            },
        )

    if current_user.balance < model.cost_per_request:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient balance",
        )

    task = TaskORM(
        user_id=current_user.id,
        model_id=model.id,
        input_file_path="inline_payload",
        status="completed",
    )
    db.add(task)
    db.flush()

    current_user.balance -= model.cost_per_request
    db.add(
        TransactionORM(
            user_id=current_user.id,
            task_id=task.id,
            amount=model.cost_per_request,
            type="debit",
        )
    )

    result = PredictionResultORM(
        task_id=task.id,
        anomalies=[],
        valid_rows_count=len(data.rows),
        invalid_rows=[],
        credits_charged=model.cost_per_request,
    )
    db.add(result)
    db.commit()
    db.refresh(task)
    db.refresh(result)
    db.refresh(current_user)

    return PredictionResponse(
        task_id=task.id,
        status=task.status,
        credits_charged=result.credits_charged,
        balance=current_user.balance,
        valid_rows_count=result.valid_rows_count,
        invalid_rows=result.invalid_rows,
        anomalies=result.anomalies,
        created_at=result.created_at,
    )


@app.get(
    "/history/predictions",
    response_model=List[PredictionHistoryResponse],
    responses={401: {"model": ErrorResponse}},
)
def get_prediction_history(
    current_user: UserORM = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    tasks = (
        db.query(TaskORM)
        .filter(TaskORM.user_id == current_user.id)
        .order_by(TaskORM.created_at.desc())
        .all()
    )

    return [
        PredictionHistoryResponse(
            task_id=task.id,
            model_id=task.model_id,
            status=task.status,
            credits_charged=task.result.credits_charged if task.result else 0.0,
            created_at=task.created_at,
        )
        for task in tasks
    ]


@app.get(
    "/history/transactions",
    response_model=List[TransactionResponse],
    responses={401: {"model": ErrorResponse}},
)
def get_transaction_history(
    current_user: UserORM = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(TransactionORM)
        .filter(TransactionORM.user_id == current_user.id)
        .order_by(TransactionORM.created_at.desc())
        .all()
    )


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", 8000))
    uvicorn.run(app, host=host, port=port)
