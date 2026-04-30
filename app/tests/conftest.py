import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from src.database import Base, get_db
from src.main import app
from src.models import MLModelORM

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)


def _override_get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def client():
    Base.metadata.create_all(bind=_engine)

    db = _Session()
    db.add(MLModelORM(name="ZScoreDetector", description="Z-score based detector", cost_per_request=2.0))
    db.commit()
    db.close()

    app.dependency_overrides[get_db] = _override_get_db

    with patch("src.main.init_db", lambda: None), \
         patch("src.routers.predict.publish_task", lambda msg: None):
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()
