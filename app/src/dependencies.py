import hashlib
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import UserORM

security = HTTPBasic()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_current_user(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> UserORM:
    user = db.query(UserORM).filter(UserORM.email == credentials.username).first()
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Basic"},
    )

    if user is None:
        raise invalid

    if not secrets.compare_digest(user.hashed_password, hash_password(credentials.password)):
        raise invalid

    return user
