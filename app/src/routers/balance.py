from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.dependencies import get_current_user
from src.models import BalanceORM, TransactionORM, UserORM
from src.schemas.balance import BalanceRequest, BalanceResponse

router = APIRouter(prefix="/balance", tags=["balance"])


def _get_balance(user: UserORM, db: Session) -> BalanceORM:
    balance = db.query(BalanceORM).filter_by(user_id=user.id).first()
    if balance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Balance account not found")
    return balance


@router.get("", response_model=BalanceResponse)
def get_balance(
    current_user: UserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    balance = _get_balance(current_user, db)
    return BalanceResponse(balance=balance.amount)


@router.post("/top-up", response_model=BalanceResponse)
def top_up(
    data: BalanceRequest,
    current_user: UserORM = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    balance = _get_balance(current_user, db)
    balance.amount += data.amount
    db.add(TransactionORM(user_id=current_user.id, amount=data.amount, type="topup"))
    db.commit()
    db.refresh(balance)
    return BalanceResponse(balance=balance.amount)
