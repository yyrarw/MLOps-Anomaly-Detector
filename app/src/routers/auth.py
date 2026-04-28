from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.dependencies import get_current_user, hash_password
from src.models import BalanceORM, UserORM
from src.schemas.auth import RegisterRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(data: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(UserORM).filter(UserORM.email == data.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = UserORM(email=data.email, hashed_password=hash_password(data.password), role="user")
    db.add(user)
    db.flush()
    db.add(BalanceORM(user_id=user.id, amount=0.0))
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=UserResponse)
def login(current_user: UserORM = Depends(get_current_user)):
    return current_user
