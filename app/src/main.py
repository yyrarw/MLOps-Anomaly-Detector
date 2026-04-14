import os
from typing import List
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database import get_db
from src.init_db import init_db
from src.models import UserORM, MLModelORM, TransactionORM, TaskORM

app = FastAPI(title="MLOps Anomaly Detector")


@app.on_event("startup")
def on_startup():
    init_db()


# Pydantic schemas

class UserCreate(BaseModel):
    email: str
    hashed_password: str
    role: str = "user"


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    balance: float
    created_at: datetime

    class Config:
        from_attributes = True


class TopUpRequest(BaseModel):
    amount: float


class DebitRequest(BaseModel):
    amount: float
    task_id: int | None = None


class TransactionResponse(BaseModel):
    id: int
    amount: float
    type: str
    task_id: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class MLModelResponse(BaseModel):
    id: int
    name: str
    description: str
    cost_per_request: float

    class Config:
        from_attributes = True


# Endpoints

@app.get("/health")
def health():
    return {"status": "ok"}


# Users

@app.post("/users", response_model=UserResponse)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(UserORM).filter_by(email=data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = UserORM(email=data.email, hashed_password=data.hashed_password, role=data.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserORM).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# Balance

@app.post("/users/{user_id}/topup", response_model=UserResponse)
def topup_balance(user_id: int, data: TopUpRequest, db: Session = Depends(get_db)):
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    user = db.query(UserORM).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.balance += data.amount
    db.add(TransactionORM(user_id=user.id, amount=data.amount, type="topup"))
    db.commit()
    db.refresh(user)
    return user


@app.post("/users/{user_id}/debit", response_model=UserResponse)
def debit_balance(user_id: int, data: DebitRequest, db: Session = Depends(get_db)):
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    user = db.query(UserORM).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.balance < data.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    user.balance -= data.amount
    db.add(TransactionORM(
        user_id=user.id, amount=data.amount, type="debit", task_id=data.task_id,
    ))
    db.commit()
    db.refresh(user)
    return user


# Transactions

@app.get("/users/{user_id}/transactions", response_model=List[TransactionResponse])
def get_transactions(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserORM).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.transactions


# ML Models

@app.get("/models", response_model=List[MLModelResponse])
def list_models(db: Session = Depends(get_db)):
    return db.query(MLModelORM).all()


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", 8000))
    uvicorn.run(app, host=host, port=port)
