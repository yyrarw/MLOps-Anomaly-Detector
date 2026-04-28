from sqlalchemy.orm import Session
from src.database import engine, SessionLocal, Base
from src.models import BalanceORM, MLModelORM, TransactionORM, UserORM


def init_db():
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        _seed_users(db)
        _seed_ml_models(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _seed_users(db: Session):
    demo_users = [
        {"email": "demo@example.com", "hashed_password": "hashed_demo_password", "role": "user", "balance": 100.0},
        {"email": "admin@example.com", "hashed_password": "hashed_admin_password", "role": "admin", "balance": 500.0},
    ]

    for data in demo_users:
        if db.query(UserORM).filter_by(email=data["email"]).first():
            continue

        user = UserORM(email=data["email"], hashed_password=data["hashed_password"], role=data["role"])
        db.add(user)
        db.flush()

        db.add(BalanceORM(user_id=user.id, amount=data["balance"]))
        db.add(TransactionORM(user_id=user.id, amount=data["balance"], type="topup"))


def _seed_ml_models(db: Session):
    models = [
        {"name": "IsolationForest", "description": "Древовидная модель для поиска аномалий в многомерных данных", "cost_per_request": 5.0},
        {"name": "ZScoreDetector", "description": "Статистический детектор на основе Z-оценки", "cost_per_request": 2.0},
        {"name": "AutoencoderDetector", "description": "Нейросетевой автоэнкодер для обнаружения аномалий", "cost_per_request": 10.0},
    ]

    for data in models:
        if not db.query(MLModelORM).filter_by(name=data["name"]).first():
            db.add(MLModelORM(**data))
