import os
import uvicorn
from fastapi import FastAPI

app = FastAPI(title="MLOps Anomaly Detector")


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", 8000))
    uvicorn.run(app, host=host, port=port)
