"""
Migration des données de l'ancien système M-Motors (export plat
"vehicules_stock") vers le nouveau schéma PostgreSQL normalisé (table
`vehicles`, voir app.models.vehicle).

Architecture : Extract → Validate → Transform → Load, chaque étape étant une
fonction pure et testable indépendamment des autres (cf. tests/test_legacy_migration.py).

Idempotent : chaque ligne source porte une référence unique (`ref_interne`),
recopiée dans `Vehicle.legacy_ref`. Relancer la migration met à jour les
véhicules déjà importés au lieu de les dupliquer.
"""

import csv
import logging
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.vehicle import Vehicle, VehicleMode

logger = logging.getLogger("etl.legacy_migration")

MIN_VALID_YEAR = 1990
CURRENT_YEAR = 2026

MOTORIZATION_MAP = {
    "essence": "Essence",
    "ess.": "Essence",
    "diesel": "Diesel",
    "electrique": "Électrique",
    "électrique": "Électrique",
    "hybride": "Hybride",
}

TRANSACTION_MAP = {
    "vente": VehicleMode.SALE,
    "location": VehicleMode.RENTAL,
    "loc. ld": VehicleMode.RENTAL,
    "location ld": VehicleMode.RENTAL,
}


@dataclass
class MigrationReport:
    """Bilan d'une exécution de migration — utile pour le dossier et les logs."""

    total_rows: int = 0
    inserted: int = 0
    updated: int = 0
    rejected: int = 0
    rejections: list[tuple[str, str]] = field(default_factory=list)  # (ref, raison)

    def log_summary(self) -> None:
        logger.info(
            "Migration terminée : %s lignes lues, %s insérées, %s mises à jour, %s rejetées",
            self.total_rows,
            self.inserted,
            self.updated,
            self.rejected,
        )
        for ref, reason in self.rejections:
            logger.warning("Ligne rejetée [%s] : %s", ref, reason)


# --- EXTRACT ---------------------------------------------------------------


def extract_rows(csv_path: Path) -> list[dict]:
    """Lit le fichier plat de l'ancien système. Une ligne = un dict brut, non nettoyé."""
    with open(csv_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --- TRANSFORM (fonctions pures, unitairement testables) -------------------


def parse_mileage(raw: str) -> int | None:
    """Retourne un kilométrage valide (entier >= 0), ou None si invalide/absent."""
    if raw is None:
        return None
    raw = raw.strip()
    if raw == "" or raw.upper() == "N/C":
        return None
    try:
        value = int(float(raw))
    except ValueError:
        return None
    return value if value >= 0 else None


def normalize_brand(raw: str) -> str:
    """Normalise la casse d'une marque (ex: 'BMW' reste 'BMW', 'ford' -> 'Ford')."""
    raw = raw.strip()
    # Marques connues pour rester en majuscules (acronymes) malgré le .title()
    if raw.upper() in {"BMW", "DAF", "MAN"}:
        return raw.upper()
    return raw.title()


def normalize_motorization(raw: str) -> str | None:
    """Mappe les variantes de casse/abréviation vers une valeur canonique FR."""
    if not raw:
        return None
    return MOTORIZATION_MAP.get(raw.strip().lower())


def parse_transaction_mode(raw: str) -> VehicleMode | None:
    """Mappe les variantes ('VENTE', 'Loc. LD', ...) vers VehicleMode."""
    if not raw:
        return None
    return TRANSACTION_MAP.get(raw.strip().lower())


def parse_price(raw: str) -> Decimal | None:
    """Parse un prix/mensualité, ou None si absent/invalide."""
    if raw is None:
        return None
    raw = raw.strip().replace("€", "").replace(",", ".")
    if raw == "":
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return value if value > 0 else None


# --- VALIDATE ----------------------------------------------------------------


def validate_and_clean(raw_row: dict) -> tuple[dict | None, str | None]:
    """
    Valide une ligne brute et la transforme en dict prêt pour `Vehicle(**dict)`.
    Retourne (donnees_nettoyees, None) si valide, ou (None, raison_du_rejet) sinon.
    """
    ref = raw_row.get("ref_interne", "?")

    brand = normalize_brand(raw_row.get("marque", ""))
    if not brand:
        return None, "marque manquante"

    try:
        year = int(raw_row.get("annee", 0))
    except (ValueError, TypeError):
        return None, "année invalide"
    if not (MIN_VALID_YEAR <= year <= CURRENT_YEAR):
        return None, f"année hors plage plausible ({year})"

    mileage = parse_mileage(raw_row.get("kilometrage"))
    if mileage is None:
        return None, "kilométrage manquant ou invalide"

    motorization = normalize_motorization(raw_row.get("carburant", ""))
    if motorization is None:
        return None, f"motorisation non reconnue ({raw_row.get('carburant')!r})"

    mode = parse_transaction_mode(raw_row.get("type_transaction", ""))
    if mode is None:
        return None, f"type de transaction non reconnu ({raw_row.get('type_transaction')!r})"

    price_eur = parse_price(raw_row.get("prix_vente"))
    monthly_price_eur = parse_price(raw_row.get("mensualite_location"))

    if mode == VehicleMode.SALE and price_eur is None:
        return None, "mode vente sans prix de vente valide"
    if mode == VehicleMode.RENTAL and monthly_price_eur is None:
        return None, "mode location sans mensualité valide"

    designation = (raw_row.get("designation") or "").strip() or "Modèle inconnu"

    return {
        "legacy_ref": ref,
        "brand": brand,
        "model": designation,
        "motorization": motorization,
        "year": year,
        "mileage_km": mileage,
        "mode": mode,
        "price_eur": price_eur,
        "monthly_price_eur": monthly_price_eur,
    }, None


# --- LOAD --------------------------------------------------------------------


def load_row(db: Session, cleaned: dict) -> str:
    """Insère ou met à jour un véhicule (upsert par legacy_ref). Retourne 'inserted'|'updated'."""
    existing = db.query(Vehicle).filter_by(legacy_ref=cleaned["legacy_ref"]).first()
    if existing is not None:
        for key, value in cleaned.items():
            setattr(existing, key, value)
        return "updated"

    db.add(Vehicle(**cleaned))
    return "inserted"


# --- ORCHESTRATION -----------------------------------------------------------


def run_migration(csv_path: Path, db: Session) -> MigrationReport:
    """Exécute la migration complète (extract → validate/transform → load)."""
    report = MigrationReport()
    raw_rows = extract_rows(csv_path)
    seen_refs: set[str] = set()

    for raw_row in raw_rows:
        report.total_rows += 1
        ref = raw_row.get("ref_interne", "?")

        # Doublon strict dans le fichier source lui-même (cf. défauts de l'ancienne base).
        if ref in seen_refs:
            report.rejected += 1
            report.rejections.append((ref, "doublon dans le fichier source"))
            continue
        seen_refs.add(ref)

        cleaned, rejection_reason = validate_and_clean(raw_row)
        if cleaned is None:
            report.rejected += 1
            report.rejections.append((ref, rejection_reason or "raison inconnue"))
            continue

        outcome = load_row(db, cleaned)
        if outcome == "inserted":
            report.inserted += 1
        else:
            report.updated += 1

    db.commit()
    report.log_summary()
    return report
