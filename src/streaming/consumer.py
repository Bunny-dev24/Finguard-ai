"""Kafka consumer — scores each transaction through the same service
layer the API uses, so the two never drift apart."""
import json
from kafka import KafkaConsumer, KafkaProducer

from src.db.session import SessionLocal, init_db
from src.ml.registry import ModelRegistry
from src.repositories.transaction_repository import TransactionRepository
from src.repositories.alert_repo import AlertRepository
from src.services.alert_service import AlertService
from src.services.scoring_service import ScoringService
from src.core.config import settings
from src.core.logging import logger


def process_record(value: dict, producer: KafkaProducer) -> None:
    """One message = one DB session. Failures here are caught and
    routed to a DLQ topic instead of bubbling up — a bad message
    shouldn't take down the whole consumer loop."""
    db = SessionLocal()
    try:
        svc = ScoringService(
            ModelRegistry.get(),
            TransactionRepository(db),
            AlertService(AlertRepository(db)))
        result = svc.score_and_persist(value)
        if result["is_fraud"]:
            producer.send(settings.kafka_alerts_topic, result)
            logger.warning(f"🚨 FRAUD {result}")
    except Exception as e:
        logger.error(f"Failed to process record "
                     f"{value.get('transaction_id', '?')}: {e}")
        producer.send(settings.kafka_dlq_topic, {"error": str(e), "record": value})
    finally:
        db.close()


def main():
    init_db()
    ModelRegistry.load()
    consumer = KafkaConsumer(
        settings.kafka_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="latest", group_id="fraud-scorer")
    producer = KafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode())

    for record in consumer:
        process_record(record.value, producer)


if __name__ == "__main__":
    main()