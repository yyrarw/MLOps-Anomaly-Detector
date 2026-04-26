from fastapi import APIRouter, Depends

from src.dependencies import get_current_user
from src.models import UserORM
from src.schemas.auth import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
def get_me(current_user: UserORM = Depends(get_current_user)):
    return current_user
