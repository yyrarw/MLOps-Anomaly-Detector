import json
import os

import pika


RABBITMQ_URL = (
    f"amqp://{os.getenv('RABBITMQ_USER', 'guest')}:"
    f"{os.getenv('RABBITMQ_PASSWORD', 'guest')}@"
    f"{os.getenv('RABBITMQ_HOST', 'rabbitmq')}:"
    f"{os.getenv('RABBITMQ_PORT', '5672')}/"
)
QUEUE_NAME = os.getenv("RABBITMQ_QUEUE", "ml_tasks")


def publish_task(message: dict) -> None:
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = connection.channel()

    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=json.dumps(message),
        properties=pika.BasicProperties(delivery_mode=2),
    )

    connection.close()
