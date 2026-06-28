"""
Point d'entrée CLI pour la migration des données legacy (US-12).

Usage :
    python scripts/migrate_legacy.py
    python scripts/migrate_legacy.py --file legacy_data/m_motors_legacy_export.csv
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.etl.legacy_migration import run_migration  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migration des données M-Motors legacy → PostgreSQL")
    parser.add_argument(
        "--file",
        default=str(Path(__file__).resolve().parent.parent / "legacy_data" / "m_motors_legacy_export.csv"),
        help="Chemin du fichier d'export de l'ancien système",
    )
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)  # garantit que la table `vehicles` existe

    db = SessionLocal()
    try:
        report = run_migration(Path(args.file), db)
    finally:
        db.close()

    print(
        f"\n{report.total_rows} lignes lues — "
        f"{report.inserted} insérées, {report.updated} mises à jour, {report.rejected} rejetées."
    )
    if report.rejected:
        print("Voir les logs ci-dessus pour le détail des rejets (traçabilité qualité des données).")


if __name__ == "__main__":
    main()
