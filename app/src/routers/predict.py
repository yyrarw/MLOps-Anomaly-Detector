import os
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.dependencies import get_current_user
from src.models import BalanceORM, MLModelORM, TaskORM, TransactionORM, UserORM
from src.publisher import publish_task
from src.schemas.predict import PredictRequest, PredictResponse

router = APIRouter(prefix="/predict", tags=["predict"])

MSK = timezone(timedelta(hours=3))

SUPPORTED_METRICS = tuple(
    m.strip()
    for m in os.getenv(
        "SUPPORTED_METRICS",
        "gpu_utilization,memory_usage,latency_ms,queue_size,tokens_per_second",
    ).split(",")
    if m.strip()
)


@router.post("", response_model=PredictResponse)
def predict(
    data: PredictRequest,
    current_user: UserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model = db.get(MLModelORM, data.model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    unsupported = sorted({row.metric for row in data.rows if row.metric not in SUPPORTED_METRICS})
    if unsupported:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Unsupported metrics in request",
                "supported_metrics": list(SUPPORTED_METRICS),
                "invalid_metrics": unsupported,
            },
        )

    balance = db.query(BalanceORM).filter_by(user_id=current_user.id).first()
    if balance is None or balance.amount < model.cost_per_request:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient balance")

    task = TaskORM(
        user_id=current_user.id,
        model_id=model.id,
        input_file_path="inline_payload",
        status="pending",
    )
    db.add(task)
    db.flush()

    balance.amount -= model.cost_per_request
    db.add(TransactionORM(
        user_id=current_user.id,
        task_id=task.id,
        amount=model.cost_per_request,
        type="debit",
    ))
    db.commit()
    db.refresh(task)
    db.refresh(balance)

    publish_task({
        "task_id": task.id,
        "model": model.name,
        "features": [row.model_dump(mode="json") for row in data.rows],
        "timestamp": datetime.now(MSK).isoformat(),
    })

    return PredictResponse(task_id=task.id, status=task.status, balance=balance.amount)
