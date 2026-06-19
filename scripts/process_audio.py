import os
import json
import uuid
import datetime
from io import BytesIO
import requests
from minio import Minio
from pymongo import MongoClient
from utils import load_config


def get_minio_client(cfg: dict) -> Minio:
    return Minio(
        cfg["endpoint"],
        access_key=cfg["access_key"],
        secret_key=cfg["secret_key"],
        secure=cfg["secure"],
    )


def ensure_bucket(client: Minio, bucket: str):
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        print(f"  Bucket '{bucket}' kreiran.")


def upload_audio(client: Minio, bucket: str, file_path: str) -> str:
    filename = os.path.basename(file_path)
    object_name = f"audio/{uuid.uuid4()}_{filename}"
    client.fput_object(bucket, object_name, file_path)
    print(f"  Uploadano: {object_name}")
    return object_name


def classify_audio(file_path: str, classify_url: str) -> dict:
    with open(file_path, "rb") as f:
        response = requests.post(classify_url, files={"file": f})
    response.raise_for_status()
    return response.json()


def save_log_to_minio(client: Minio, bucket: str, log: dict, object_name: str):
    log_name = f"logs/{object_name.replace('/', '_')}.json"
    log_bytes = json.dumps(log, indent=2).encode("utf-8")
    client.put_object(bucket, log_name, BytesIO(log_bytes), len(log_bytes),
                      content_type="application/json")
    print(f"  Log spremljen: {log_name}")


def save_result_to_mongo(collection, file_path: str, object_name: str,
                         classification: dict, location: dict):
    doc = {
        "filename":       os.path.basename(file_path),
        "minio_object":   object_name,
        "location":       location,
        "classification": classification,
        "processed_at":   datetime.datetime.now(datetime.UTC),
    }
    collection.insert_one(doc)


def process_audio_files(config: dict):
    minio_cfg  = config["minio"]
    mongo_uri  = config["mongodb"]["uri"]
    db_name    = config["mongodb"]["database"]
    audio_dir  = config["audio"]["local_dir"]
    classify_url = config["aves_api"]["classify_url"]

    location     = config["audio"]["default_location"]

    minio_client = get_minio_client(minio_cfg)
    ensure_bucket(minio_client, minio_cfg["bucket"])

    audio_files = [
        os.path.join(audio_dir, f)
        for f in os.listdir(audio_dir)
        if f.lower().endswith((".mp3", ".wav", ".ogg", ".flac"))
    ]

    if not audio_files:
        print("  Nema audio datoteka u direktoriju.")
        return

    print(f"  Pronađeno {len(audio_files)} audio datoteka.")

    with MongoClient(mongo_uri) as mongo_client:
        collection = mongo_client[db_name]["classifications"]

        for file_path in audio_files:
            print(f"\n  Obrađujem: {file_path}")

            # 1. Upload u MinIO
            object_name = upload_audio(minio_client, minio_cfg["bucket"], file_path)

            # 2. Klasifikacija
            try:
                result = classify_audio(file_path, classify_url)
                print(f"  Klasifikacija: {json.dumps(result)[:200]}")
            except Exception as e:
                print(f"  Greška klasifikacije: {e}")
                result = {"error": str(e)}

            # 3. Log u MinIO
            log = {
                "file":         os.path.basename(file_path),
                "minio_object": object_name,
                "location":     location,
                "response":     result,
                "timestamp":    datetime.datetime.now(datetime.UTC).isoformat(),
            }
            save_log_to_minio(minio_client, minio_cfg["bucket"], log, object_name)

            # 4. Rezultat u MongoDB
            save_result_to_mongo(collection, file_path, object_name, result, location)
            print(f"  Rezultat spremljen u MongoDB.")

    print(f"\n  Ukupno obrađeno: {len(audio_files)} datoteka.")


if __name__ == "__main__":
    config = load_config()
    print("[3/4] Obrađujem audio datoteke...")
    process_audio_files(config)
    print("[3/4] Gotovo.")