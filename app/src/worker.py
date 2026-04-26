import json
import logging
import os
import random
import time

import pika

from src.database import SessionLocal
from src.models import PredictionResultORM, TaskORM

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


def _mock_predict(features: list) -> list:
    anomalies = []
    for row in features:
        score = random.uniform(0, 1)
        if score > 0.8:
            anomalies.append({
                "metric": row.get("metric"),
                "node": row.get("node"),
                "value": row.get("value"),
                "anomaly_score": round(score, 4),
            })
    return anomalies


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
    log.info("[%s] Processing task %s (model=%s)", WORKER_ID, task_id, data["model"])

    anomalies = _mock_predict(data["features"])

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

        result = PredictionResultORM(
            task_id=task_id,
            anomalies=anomalies,
            valid_rows_count=len(features),
            invalid_rows=[],
            credits_charged=0.0,
        )
        db.add(result)
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
        if task:
            task.status = "failed"
            db.commit()
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
