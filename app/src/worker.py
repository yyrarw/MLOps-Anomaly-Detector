import json
import logging
import os
import re
import time

import numpy as np
import pika
import requests
from sklearn.ensemble import IsolationForest

from src.database import SessionLocal
from src.models import BalanceORM, PredictionResultORM, TaskORM, TransactionORM

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

WORKER_ID = os.getenv("WORKER_ID", "worker-1")
RABBITMQ_URL = (
    f"amqp://{os.getenv('RABBITMQ_USER', 'guest')}:"
    f"{os.getenv('RABBITMQ_PASSWORD', 'guest')}@"
    f"{os.getenv('RABBITMQ_HOST', 'rabbitmq')}:"
    f"{os.getenv('RABBITMQ_PORT', '5672')}/"
)
QUEUE_NAME = os.getenv("RABBITMQ_QUEUE", "ml_tasks")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = "tinyllama"


# --- ML models ---

def _predict_zscore(features: list) -> list:
    """Z-score per metric: anomaly if |z| > 2.5."""
    from collections import defaultdict

    groups = defaultdict(list)
    for i, row in enumerate(features):
        groups[row["metric"]].append((i, float(row["value"])))

    anomaly_indices = set()
    scores = {}
    for metric, items in groups.items():
        if len(items) < 2:
            continue
        indices, values = zip(*items)
        arr = np.array(values)
        mean, std = arr.mean(), arr.std()
        if std == 0:
            continue
        for idx, val in zip(indices, values):
            z = abs((val - mean) / std)
            if z > 2.5:
                anomaly_indices.add(idx)
                scores[idx] = round(z, 4)

    return [
        {
            "metric": features[i]["metric"],
            "node": features[i]["node"],
            "value": features[i]["value"],
            "anomaly_score": scores[i],
            "method": "zscore",
        }
        for i in anomaly_indices
    ]


def _predict_isolation_forest(features: list) -> list:
    """IsolationForest on (value) per metric group."""
    from collections import defaultdict

    if len(features) < 2:
        return []

    groups = defaultdict(list)
    for i, row in enumerate(features):
        groups[row["metric"]].append((i, float(row["value"])))

    anomaly_indices = set()
    for metric, items in groups.items():
        if len(items) < 2:
            continue
        indices, values = zip(*items)
        X = np.array(values).reshape(-1, 1)
        clf = IsolationForest(contamination=0.1, random_state=42)
        preds = clf.fit_predict(X)
        scores = clf.score_samples(X)
        for idx, pred, score in zip(indices, preds, scores):
            if pred == -1:
                anomaly_indices.add((idx, round(float(-score), 4)))

    return [
        {
            "metric": features[idx]["metric"],
            "node": features[idx]["node"],
            "value": features[idx]["value"],
            "anomaly_score": score,
            "method": "isolation_forest",
        }
        for idx, score in anomaly_indices
    ]


def _predict_llm(features: list) -> list:
    """TinyLlama via Ollama: LLM-based anomaly detection."""
    prompt = (
        "You are an anomaly detection system for infrastructure metrics. "
        "Analyze the data below and find anomalies.\n\n"
        f"Data:\n{json.dumps(features, indent=2)}\n\n"
        "Rules:\n"
        "- gpu_utilization > 90 is anomalous\n"
        "- memory_usage > 85 is anomalous\n"
        "- latency_ms > 1000 is anomalous\n"
        "- queue_size > 100 is anomalous\n"
        "- A value much higher or lower than others of the same metric is anomalous\n\n"
        "Return ONLY a valid JSON array of anomalies. "
        "Each item must have: metric, node, value, reason. "
        "If no anomalies, return []. No explanation, only JSON."
    )

    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        r.raise_for_status()
        raw = r.json().get("response", "")
        log.debug("[%s] LLM raw response: %s", WORKER_ID, raw)

        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if not match:
            log.warning("[%s] LLM returned no JSON array, returning empty", WORKER_ID)
            return []

        anomalies = json.loads(match.group())
        for a in anomalies:
            a["method"] = "llm_tinyllama"
        return anomalies

    except requests.exceptions.RequestException as exc:
        log.error("[%s] Ollama request failed: %s", WORKER_ID, exc)
        return []
    except json.JSONDecodeError as exc:
        log.error("[%s] Failed to parse LLM JSON: %s", WORKER_ID, exc)
        return []


MODEL_PREDICTORS = {
    "ZScoreDetector": _predict_zscore,
    "IsolationForest": _predict_isolation_forest,
    "AutoencoderDetector": _predict_llm,
}


# --- Message handling ---

def _validate_message(data: dict) -> str | None:
    required = {"task_id", "model", "features", "timestamp"}
    missing = required - data.keys()
    if missing:
        return f"Missing fields: {missing}"
    if not isinstance(data["features"], list) or not data["features"]:
        return "features must be a non-empty list"
    return None


def _process_message(body: bytes) -> None:
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        log.error("[%s] Invalid JSON: %s", WORKER_ID, exc)
        return

    error = _validate_message(data)
    if error:
        log.error("[%s] Validation failed for task %s: %s", WORKER_ID, data.get("task_id"), error)
        _mark_task_failed(data.get("task_id"))
        return

    task_id = data["task_id"]
    model_name = data["model"]
    log.info("[%s] Processing task %s (model=%s)", WORKER_ID, task_id, model_name)

    predictor = MODEL_PREDICTORS.get(model_name, _predict_zscore)
    try:
        anomalies = predictor(data["features"])
    except Exception as exc:
        log.error("[%s] Predictor failed for task %s: %s", WORKER_ID, task_id, exc)
        _mark_task_failed(task_id)
        return

    _save_result(task_id, features=data["features"], anomalies=anomalies)
    log.info("[%s] Task %s done — anomalies found: %d", WORKER_ID, task_id, len(anomalies))


def _save_result(task_id: int, features: list, anomalies: list) -> None:
    db = SessionLocal()
    try:
        task = db.query(TaskORM).get(task_id)
        if task is None:
            log.error("[%s] Task %s not found in DB", WORKER_ID, task_id)
            return
        task.status = "completed"
        debit = db.query(TransactionORM).filter_by(task_id=task_id, type="debit").first()
        credits_charged = debit.amount if debit else 0.0
        db.add(PredictionResultORM(
            task_id=task_id,
            anomalies=anomalies,
            valid_rows_count=len(features),
            invalid_rows=[],
            credits_charged=credits_charged,
        ))
        db.commit()
    except Exception as exc:
        db.rollback()
        log.error("[%s] DB error for task %s: %s", WORKER_ID, task_id, exc)
    finally:
        db.close()


def _mark_task_failed(task_id) -> None:
    if task_id is None:
        return
    db = SessionLocal()
    try:
        task = db.query(TaskORM).get(task_id)
        if task is None:
            return
        task.status = "failed"
        debit = (
            db.query(TransactionORM)
            .filter_by(task_id=task_id, type="debit")
            .first()
        )
        if debit:
            balance = db.query(BalanceORM).filter_by(user_id=task.user_id).first()
            if balance:
                balance.amount += debit.amount
                db.add(TransactionORM(
                    user_id=task.user_id,
                    task_id=task_id,
                    amount=debit.amount,
                    type="topup",
                ))
        db.commit()
    except Exception as exc:
        db.rollback()
        log.error("[%s] Failed to mark task %s as failed: %s", WORKER_ID, task_id, exc)
    finally:
        db.close()


def _on_message(channel, method, properties, body):
    _process_message(body)
    channel.basic_ack(delivery_tag=method.delivery_tag)


def run():
    while True:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=_on_message)
            log.info("[%s] Waiting for tasks in queue '%s'...", WORKER_ID, QUEUE_NAME)
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            log.warning("[%s] RabbitMQ unavailable, retrying in 5s...", WORKER_ID)
            time.sleep(5)


if __name__ == "__main__":
    run()
