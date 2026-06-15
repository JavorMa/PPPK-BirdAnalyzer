import json
import yaml
from kafka import KafkaConsumer
from pymongo import MongoClient


def load_config():
    with open("config.yaml") as f:
        return yaml.safe_load(f)


def consume_observations(kafka_cfg: dict, mongo_uri: str, db_name: str):
    consumer = KafkaConsumer(
        kafka_cfg["topic"],
        bootstrap_servers=kafka_cfg["bootstrap_servers"],
        group_id=kafka_cfg["group_id"],
        auto_offset_reset="earliest",       # čitaj od početka
        enable_auto_commit=True,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        consumer_timeout_ms=10000,           # zaustavi se nakon 5s bez novih poruka
    )

    client = MongoClient(mongo_uri)
    collection = client[db_name]["observations"]

    inserted = 0
    for message in consumer:
        observation = message.value

        # Validacija — mora imati taxonKey i lokaciju
        if "taxonKey" not in observation:
            print(f"  Preskačem poruku bez taxonKey: {observation}")
            continue
        if "latitude" not in observation or "longitude" not in observation:
            print(f"  Preskačem poruku bez lokacije: {observation}")
            continue

        # Dodaj Kafka metadata
        observation["_kafka_partition"] = message.partition
        observation["_kafka_offset"]    = message.offset

        collection.insert_one(observation)
        inserted += 1
        print(f"  Opažanje umetnutno: taxonKey={observation['taxonKey']} | "
              f"lat={observation['latitude']}, lon={observation['longitude']}")

    consumer.close()
    client.close()
    print(f"  Ukupno umetnutno opažanja: {inserted}")


if __name__ == "__main__":
    config = load_config()
    print("[2/4] Čitam Kafka poruke...")
    consume_observations(
        config["kafka"],
        config["mongodb"]["uri"],
        config["mongodb"]["database"]
    )
    print("[2/4] Gotovo.")