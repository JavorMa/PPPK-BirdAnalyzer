import json
from kafka import KafkaConsumer
from pymongo import MongoClient
from utils import load_config


def consume_observations(kafka_cfg: dict, mongo_uri: str, db_name: str):
    consumer = KafkaConsumer(
        kafka_cfg["topic"],
        bootstrap_servers=kafka_cfg["bootstrap_servers"],
        group_id=kafka_cfg["group_id"],
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        consumer_timeout_ms=10000,  # zaustavi se nakon 10s bez novih poruka
    )

    inserted = 0
    try:
        with MongoClient(mongo_uri) as client:
            collection = client[db_name]["observations"]

            try:
                for message in consumer:
                    observation = message.value

                    if "taxonKey" not in observation:
                        print(f"  Preskačem poruku bez taxonKey: {observation}")
                        continue
                    if "latitude" not in observation or "longitude" not in observation:
                        print(f"  Preskačem poruku bez lokacije: {observation}")
                        continue

                    observation["_kafka_partition"] = message.partition
                    observation["_kafka_offset"]    = message.offset

                    collection.insert_one(observation)
                    inserted += 1
                    print(f"  Opažanje umetnutno: taxonKey={observation['taxonKey']} | "
                          f"lat={observation['latitude']}, lon={observation['longitude']}")
            except ValueError:
                pass  # kafka-python-ng / Python 3.13 Windows kompatibilnost
    finally:
        try:
            consumer.close()
        except Exception:
            pass

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