import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = (
    f"postgresql://{os.getenv('DATABASE_USER', 'postgres')}:"
    f"{os.getenv('DATABASE_PASSWORD', 'postgres')}@"
    f"{os.getenv('DATABASE_HOST', 'localhost')}:"
    f"{os.getenv('DATABASE_PORT', '5432')}/"
    f"{os.getenv('DATABASE_NAME', 'anomaly_detector')}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
