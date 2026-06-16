import sys
import pandas as pd
from pymongo import MongoClient
from thefuzz import fuzz
from utils import load_config


def get_species_filter() -> str | None:
    """Čita opcionalni fuzzy filter iz argumenta komandne linije."""
    return sys.argv[1] if len(sys.argv) > 1 else None


def load_classifications(db) -> list[dict]:
    """Dohvaća sve klasifikacije koje imaju barem jedan rezultat."""
    return [
        doc for doc in db["classifications"].find()
        if "results" in doc.get("classification", {})
        and len(doc["classification"]["results"]) > 0
    ]


def load_species_map(db) -> dict:
    """Gradi rječnik canonicalName → species info iz MongoDB."""
    return {
        s.get("canonicalName", ""): s
        for s in db["species"].find()
        if s.get("canonicalName")
    }


def fuzzy_match(name: str, query: str, threshold: int = 60) -> bool:
    """Vraća True ako naziv vrste dovoljno odgovara query stringu."""
    return fuzz.partial_ratio(query.lower(), name.lower()) >= threshold


def build_rows(classifications: list[dict], species_map: dict,
               species_filter: str | None) -> list[dict]:
    rows = []

    for doc in classifications:
        results = doc["classification"]["results"]
        location = doc.get("location", {})

        for result in results:
            scientific_name = result.get("scientific_name", "")
            common_name     = result.get("common_name", "")
            confidence      = result.get("confidence", 0)

            # Fuzzy filter — ako je postavljen
            if species_filter:
                if not (fuzzy_match(scientific_name, species_filter) or
                        fuzzy_match(common_name, species_filter)):
                    continue

            # Dohvati taksonomske podatke iz MongoDB
            species_info = species_map.get(scientific_name, {})

            rows.append({
                "scientific_name": scientific_name,
                "common_name":     common_name,
                "confidence":      round(confidence, 4),
                "start_time":      result.get("start_time"),
                "end_time":        result.get("end_time"),
                "latitude":        location.get("latitude"),
                "longitude":       location.get("longitude"),
                "filename":        doc.get("filename"),
                "family":          species_info.get("family", ""),
                "order":           species_info.get("order", ""),
                "kingdom":         species_info.get("kingdom", ""),
            })

    return rows


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Čišćenje i transformacije podataka."""
    # Ukloni duplikate
    df = df.drop_duplicates()

    # Ukloni redove bez scientific_name
    df = df[df["scientific_name"].notna() & (df["scientific_name"] != "")]

    # Confidence kao postotak zaokružen na 2 decimale
    df["confidence_pct"] = (df["confidence"] * 100).round(2)

    # Sortiraj po confidence silazno
    df = df.sort_values("confidence", ascending=False)

    return df.reset_index(drop=True)


def generate_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Generira statistiku po vrsti."""
    return (
        df.groupby(["scientific_name", "common_name", "family", "order"])
        .agg(
            num_classifications=("confidence", "count"),
            avg_confidence=("confidence", "mean"),
            max_confidence=("confidence", "max"),
        )
        .round(4)
        .reset_index()
        .sort_values("num_classifications", ascending=False)
    )


if __name__ == "__main__":
    config       = load_config()
    species_filter = get_species_filter()

    print("[4/4] Generiram CSV izvještaj...")
    if species_filter:
        print(f"  Fuzzy filter: '{species_filter}'")

    with MongoClient(config["mongodb"]["uri"]) as client:
        db              = client[config["mongodb"]["database"]]
        classifications = load_classifications(db)
        species_map     = load_species_map(db)

    print(f"  Pronađeno {len(classifications)} klasifikacija s rezultatima.")

    rows = build_rows(classifications, species_map, species_filter)

    if not rows:
        print("  Nema podataka za izvještaj (provjeri filter).")
        sys.exit(0)

    df      = clean_data(pd.DataFrame(rows))
    summary = generate_summary(df)

    output_path = config["output"]["csv_path"]
    df.to_csv(output_path, index=False)
    print(f"  Detaljni CSV spremljen: {output_path}")

    summary_path = output_path.replace(".csv", "_summary.csv")
    summary.to_csv(summary_path, index=False)
    print(f"  Summary CSV spremljen: {summary_path}")

    print("\n  === Statistika po vrsti ===")
    print(summary.to_string(index=False))

    print("\n[4/4] Gotovo.")