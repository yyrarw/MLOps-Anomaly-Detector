from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.dependencies import get_current_user
from src.models import TaskORM, TransactionORM, UserORM
from src.schemas.balance import TransactionResponse
from src.schemas.predict import PredictionHistoryResponse, TaskDetailResponse

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/predictions", response_model=List[PredictionHistoryResponse])
def get_prediction_history(
    current_user: UserORM = Depends(get_current_user),
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


@router.get("/predictions/{task_id}", response_model=TaskDetailResponse)
def get_task_detail(
    task_id: int,
    current_user: UserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.query(TaskORM).filter(TaskORM.id == task_id, TaskORM.user_id == current_user.id).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskDetailResponse(
        task_id=task.id,
        model_id=task.model_id,
        status=task.status,
        credits_charged=task.result.credits_charged if task.result else 0.0,
        created_at=task.created_at,
        anomalies=task.result.anomalies if task.result else None,
    )


@router.get("/transactions", response_model=List[TransactionResponse])
def get_transaction_history(
    current_user: UserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(TransactionORM)
        .filter(TransactionORM.user_id == current_user.id)
        .order_by(TransactionORM.created_at.desc())
        .all()
    )
