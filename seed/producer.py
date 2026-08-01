"""Seed the Lenses CE Kafka with the synthetic ETD lifecycle.

Event generation and ground truth live in seed/lifecycle.py (pure, no
Kafka) -- this module only creates topics and sends.

Env: KAFKA_BOOTSTRAP (default localhost:19092 -- check `docker compose
ps` on your Lenses CE stack for the advertised listener).
"""

import json
import os
from pathlib import Path

from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic

from lifecycle import TOPIC_CONFIGS, generate

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:19092")


def ensure_topics():
    admin = KafkaAdminClient(bootstrap_servers=BOOTSTRAP)
    existing = set(admin.list_topics())
    new = [
        NewTopic(name=t, num_partitions=3, replication_factor=1,
                 topic_configs=cfg)
        for t, cfg in TOPIC_CONFIGS.items() if t not in existing
    ]
    if new:
        admin.create_topics(new)
    admin.close()


def main():
    events, truth = generate()
    ensure_topics()
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        key_serializer=lambda k: k.encode(),
        value_serializer=lambda v: json.dumps(v, default=str).encode(),
    )
    for topic, key, value in events:
        producer.send(topic, key=key, value=value)
    producer.flush()

    out = Path(__file__).resolve().parent.parent / "exports" / "ground_truth.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(truth, indent=2, default=str))
    print(f"sent {len(events)} events to {BOOTSTRAP}; ground truth -> {out}")


if __name__ == "__main__":
    main()
