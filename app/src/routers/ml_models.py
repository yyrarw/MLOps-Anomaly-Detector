from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import MLModelORM
from src.schemas.ml_model import MLModelResponse

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=List[MLModelResponse])
def list_models(db: Session = Depends(get_db)):
    return db.query(MLModelORM).all()
