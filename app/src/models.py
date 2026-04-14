from datetime import datetime, timezone, timedelta
from sqlalchemy import (
    Column, Integer, String, Float, Enum as SAEnum,
    ForeignKey, DateTime, Text, JSON,
)
from sqlalchemy.orm import relationship
from src.database import Base

MSK = timezone(timedelta(hours=3))


class UserORM(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum("user", "admin", name="user_role"), default="user", nullable=False)
    balance = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(MSK))

    transactions = relationship("TransactionORM", back_populates="user", order_by="TransactionORM.created_at.desc()")
    tasks = relationship("TaskORM", back_populates="user", order_by="TaskORM.created_at.desc()")


class MLModelORM(Base):
    __tablename__ = "ml_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, default="")
    cost_per_request = Column(Float, nullable=False)

    tasks = relationship("TaskORM", back_populates="model")


class TaskORM(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    model_id = Column(Integer, ForeignKey("ml_models.id"), nullable=False)
    input_file_path = Column(String(500), nullable=False)
    status = Column(
        SAEnum("pending", "processing", "completed", "failed", name="task_status"),
        default="pending",
        nullable=False,
    )
    created_at = Column(DateTime, default=lambda: datetime.now(MSK))

    user = relationship("UserORM", back_populates="tasks")
    model = relationship("MLModelORM", back_populates="tasks")
    transactions = relationship("TransactionORM", back_populates="task")
    result = relationship("PredictionResultORM", back_populates="task", uselist=False)


class TransactionORM(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    amount = Column(Float, nullable=False)
    type = Column(SAEnum("topup", "debit", name="transaction_type"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(MSK))

    user = relationship("UserORM", back_populates="transactions")
    task = relationship("TaskORM", back_populates="transactions")


class PredictionResultORM(Base):
    __tablename__ = "prediction_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    anomalies = Column(JSON, default=list)
    valid_rows_count = Column(Integer, default=0)
    invalid_rows = Column(JSON, default=list)
    credits_charged = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(MSK))

    task = relationship("TaskORM", back_populates="result")
