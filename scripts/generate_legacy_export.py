"""
Génère legacy_data/m_motors_legacy_export.csv : un export simulé de l'ANCIEN
système M-Motors (table plate "vehicules_stock", non normalisée).

Source réelle : legacy_data/source_real_specs.csv — 37 fiches techniques de
véhicules réels (marque/modèle/année/motorisation/prix neuf), extrait public
du dataset vbalagovic/cars-dataset (échantillon, licence MIT, GitHub).

Ce script :
1. Part de ces 37 véhicules réels (prix CATALOGUE NEUF).
2. Simule plusieurs unités de stock par modèle (un concessionnaire a
   plusieurs exemplaires d'un même modèle), avec un âge et un kilométrage
   plausibles, et un prix d'occasion calculé par décote réaliste
   (âge + kilométrage), pas le prix neuf brut.
3. Injecte volontairement des défauts typiques d'une vieille base de
   données (casse incohérente, valeurs manquantes, doublons, kilométrage
   invalide) — c'est précisément ce que le script de migration (US-12)
   doit détecter et nettoyer.

Usage : python scripts/generate_legacy_export.py
"""

import csv
import random
from datetime import date
from pathlib import Path

random.seed(42)  # reproductible

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_FILE = BASE_DIR / "legacy_data" / "source_real_specs.csv"
OUTPUT_FILE = BASE_DIR / "legacy_data" / "m_motors_legacy_export.csv"

CURRENT_YEAR = 2026

FUEL_TO_MOTORISATION_VARIANTS = {
    "gasoline": ["Essence", "essence", "ESSENCE", "Ess."],
    "diesel": ["Diesel", "diesel", "DIESEL"],
    "electric": ["Électrique", "electrique", "ELECTRIQUE", "Electrique"],
    "hybrid": ["Hybride", "hybride", "HYBRIDE"],
}

TRANSACTION_VARIANTS = {
    "sale": ["VENTE", "vente", "Vente"],
    "rental": ["LOCATION", "location", "Loc. LD", "LOCATION LD"],
}


def load_real_specs():
    with open(SOURCE_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def depreciated_price(new_price: float, age_years: int, mileage_km: int) -> float:
    """Décote simplifiée : ~15%/an + 0.01€ par km, plancher à 12% du prix neuf."""
    factor = max(0.12, 1 - (0.15 * age_years) - (mileage_km * 0.000004))
    return round(new_price * factor, 2)


def build_rows(specs):
    rows = []
    ref_counter = 1

    for spec in specs:
        brand = spec["brand"]
        model = spec["model"]
        base_year = int(float(spec["year"]))
        new_price = float(spec["price_eur"])
        fuel = spec["fuel_type"]

        units = random.randint(2, 5)  # plusieurs exemplaires en stock par modèle
        for _ in range(units):
            age = random.randint(1, max(1, CURRENT_YEAR - base_year + 2))
            registration_year = CURRENT_YEAR - age
            mileage = max(500, int(random.gauss(age * 16000, age * 4000)))
            transaction_type = random.choices(["sale", "rental"], weights=[65, 35])[0]
            used_price = depreciated_price(new_price, age, mileage)

            row = {
                "ref_interne": f"MM-{ref_counter:04d}",
                "marque": brand,
                "designation": f"{model} ({spec.get('trim', '').strip()})" if spec.get("trim") else model,
                "annee": registration_year,
                "kilometrage": mileage,
                "carburant": random.choice(FUEL_TO_MOTORISATION_VARIANTS.get(fuel, ["Essence"])),
                "type_transaction": random.choice(TRANSACTION_VARIANTS[transaction_type]),
                "prix_vente": used_price if transaction_type == "sale" else "",
                "mensualite_location": round(used_price / 48, 2) if transaction_type == "rental" else "",
                "date_export": date(2026, 6, 20).isoformat(),
            }
            rows.append(row)
            ref_counter += 1

    return rows


def inject_legacy_defects(rows):
    """Défauts typiques d'une vieille base : valeurs manquantes, doublons, données invalides."""
    n = len(rows)

    # ~5% de kilométrage manquant
    for i in random.sample(range(n), max(1, n // 20)):
        rows[i]["kilometrage"] = random.choice(["", "N/C"])

    # quelques kilométrages invalides (erreur de saisie)
    for i in random.sample(range(n), 3):
        rows[i]["kilometrage"] = random.choice([-500, "abc"])

    # quelques doublons stricts (même ref, même ligne) — test d'idempotence de l'ETL
    duplicates = [dict(rows[i]) for i in random.sample(range(n), 3)]
    rows.extend(duplicates)

    random.shuffle(rows)
    return rows


def main():
    specs = load_real_specs()
    rows = build_rows(specs)
    rows = inject_legacy_defects(rows)

    fieldnames = [
        "ref_interne",
        "marque",
        "designation",
        "annee",
        "kilometrage",
        "carburant",
        "type_transaction",
        "prix_vente",
        "mensualite_location",
        "date_export",
    ]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)} lignes écrites dans {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
