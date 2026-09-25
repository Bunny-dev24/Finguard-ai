import json, time, uuid
from kafka import KafkaProducer
from data.generate_data import generate
from src.core.config import settings


def main(rate_per_sec: float = 20):
    producer = KafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode())
    # velocity fields get computed server-side, don't send them here
    df = generate(20000).drop(columns=["is_fraud", "user_avg_amount", "txn_count_1h"])
    for _, row in df.iterrows():
        msg = row.to_dict()
        msg["timestamp"] = str(msg["timestamp"])
        msg["transaction_id"] = str(uuid.uuid4())
        producer.send(settings.kafka_topic, msg)
        time.sleep(1 / rate_per_sec)
    producer.flush()


if __name__ == "__main__":
    main()