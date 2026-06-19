import requests
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from utils import load_config


def fetch_all_species(base_url: str) -> list[dict]:
    print("  Dohvaćam aves.json...")
    response = requests.get(f"{base_url}/aves.json")
    response.raise_for_status()
    data = response.json()
    print(f"  Ukupno vrsta u JSON-u: {len(data)}")
    return data


def save_to_mongo(species: list[dict], mongo_uri: str, db_name: str):
    with MongoClient(mongo_uri) as client:
        collection = client[db_name]["species"]
        collection.create_index("key", unique=True)

        inserted = skipped = 0
        for s in species:
            try:
                collection.insert_one(s)
                inserted += 1
            except DuplicateKeyError:
                skipped += 1

        print(f"  Umetnutno: {inserted}, preskočeno (duplikati): {skipped}")


if __name__ == "__main__":
    config = load_config()
    print("[1/4] Dohvaćam taksonomske podatke...")
    species = fetch_all_species(config["aves_api"]["base_url"])
    save_to_mongo(species, config["mongodb"]["uri"], config["mongodb"]["database"])
    print("[1/4] Gotovo.")