import os

import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException

from src.errors import http_exception_handler, unhandled_exception_handler, validation_exception_handler
from src.init_db import init_db
from src.routers import auth, balance, history, ml_models, predict, users

app = FastAPI(title="MLOps Anomaly Detector")

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(balance.router)
app.include_router(ml_models.router)
app.include_router(predict.router)
app.include_router(history.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", 8000))
    uvicorn.run(app, host=host, port=port)
