from decimal import Decimal
from pathlib import Path

from app.etl.legacy_migration import (
    normalize_brand,
    normalize_motorization,
    parse_mileage,
    parse_price,
    parse_transaction_mode,
    run_migration,
    validate_and_clean,
)
from app.models.vehicle import Vehicle, VehicleMode

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestParseMileage:
    def test_valid_integer_string(self):
        assert parse_mileage("45000") == 45000

    def test_valid_float_string(self):
        assert parse_mileage("45000.0") == 45000

    def test_empty_string_is_none(self):
        assert parse_mileage("") is None

    def test_nc_marker_is_none(self):
        assert parse_mileage("N/C") is None

    def test_negative_is_none(self):
        assert parse_mileage("-500") is None

    def test_non_numeric_is_none(self):
        assert parse_mileage("abc") is None


class TestNormalizeBrand:
    def test_lowercase_is_title_cased(self):
        assert normalize_brand("ford") == "Ford"

    def test_acronym_stays_uppercase(self):
        assert normalize_brand("bmw") == "BMW"

    def test_strips_whitespace(self):
        assert normalize_brand("  Audi  ") == "Audi"


class TestNormalizeMotorization:
    def test_known_variants_map_to_canonical(self):
        assert normalize_motorization("ESSENCE") == "Essence"
        assert normalize_motorization("Ess.") == "Essence"
        assert normalize_motorization("diesel") == "Diesel"
        assert normalize_motorization("electrique") == "Électrique"
        assert normalize_motorization("HYBRIDE") == "Hybride"

    def test_unknown_value_returns_none(self):
        assert normalize_motorization("hydrogene") is None

    def test_empty_returns_none(self):
        assert normalize_motorization("") is None


class TestParseTransactionMode:
    def test_sale_variants(self):
        assert parse_transaction_mode("VENTE") == VehicleMode.SALE
        assert parse_transaction_mode("vente") == VehicleMode.SALE

    def test_rental_variants(self):
        assert parse_transaction_mode("LOCATION") == VehicleMode.RENTAL
        assert parse_transaction_mode("Loc. LD") == VehicleMode.RENTAL

    def test_unknown_returns_none(self):
        assert parse_transaction_mode("LEASING") is None


class TestParsePrice:
    def test_plain_number(self):
        assert parse_price("15000.50") == Decimal("15000.50")

    def test_with_euro_symbol_and_comma(self):
        assert parse_price("15000,50€") == Decimal("15000.50")

    def test_empty_is_none(self):
        assert parse_price("") is None

    def test_zero_is_none(self):
        assert parse_price("0") is None


class TestValidateAndClean:
    VALID_ROW = {
        "ref_interne": "MM-0001",
        "marque": "peugeot",
        "designation": "308 (GT Line)",
        "annee": "2022",
        "kilometrage": "35000",
        "carburant": "Diesel",
        "type_transaction": "VENTE",
        "prix_vente": "15000",
        "mensualite_location": "",
    }

    def test_valid_sale_row_is_cleaned(self):
        cleaned, reason = validate_and_clean(self.VALID_ROW)

        assert reason is None
        assert cleaned["brand"] == "Peugeot"
        assert cleaned["mode"] == VehicleMode.SALE
        assert cleaned["price_eur"] == Decimal("15000")
        assert cleaned["legacy_ref"] == "MM-0001"

    def test_valid_rental_row_requires_monthly_price(self):
        row = {**self.VALID_ROW, "type_transaction": "LOCATION", "prix_vente": "", "mensualite_location": "300"}
        cleaned, reason = validate_and_clean(row)

        assert reason is None
        assert cleaned["mode"] == VehicleMode.RENTAL
        assert cleaned["monthly_price_eur"] == Decimal("300")

    def test_sale_without_price_is_rejected(self):
        row = {**self.VALID_ROW, "prix_vente": ""}
        cleaned, reason = validate_and_clean(row)

        assert cleaned is None
        assert "prix" in reason

    def test_invalid_mileage_is_rejected(self):
        row = {**self.VALID_ROW, "kilometrage": "N/C"}
        cleaned, reason = validate_and_clean(row)

        assert cleaned is None
        assert "kilom" in reason

    def test_unknown_motorization_is_rejected(self):
        row = {**self.VALID_ROW, "carburant": "hydrogene"}
        cleaned, reason = validate_and_clean(row)

        assert cleaned is None
        assert "motorisation" in reason

    def test_year_out_of_range_is_rejected(self):
        row = {**self.VALID_ROW, "annee": "1950"}
        cleaned, reason = validate_and_clean(row)

        assert cleaned is None
        assert "année" in reason


class TestRunMigrationIntegration:
    """Test de bout en bout : CSV -> base, avec un petit fichier de fixture dédié."""

    def _write_fixture(self, tmp_path, rows: list[str]) -> Path:
        header = "ref_interne,marque,designation,annee,kilometrage,carburant,type_transaction,prix_vente,mensualite_location,date_export\n"
        csv_path = tmp_path / "legacy_fixture.csv"
        csv_path.write_text(header + "\n".join(rows), encoding="utf-8")
        return csv_path

    def test_migration_inserts_valid_rows_and_rejects_invalid(self, db_session, tmp_path):
        csv_path = self._write_fixture(
            db_session and tmp_path,
            [
                "MM-1,Peugeot,308,2022,35000,Diesel,VENTE,15000,,2026-06-20",
                "MM-2,renault,Clio,2021,N/C,Essence,VENTE,9000,,2026-06-20",  # km invalide -> rejet
                "MM-3,BMW,X3,2020,60000,diesel,LOCATION,,450,2026-06-20",
            ],
        )

        report = run_migration(csv_path, db_session)

        assert report.total_rows == 3
        assert report.inserted == 2
        assert report.rejected == 1

        vehicles = db_session.query(Vehicle).all()
        brands = {v.brand for v in vehicles}
        assert brands == {"Peugeot", "BMW"}

    def test_migration_is_idempotent(self, db_session, tmp_path):
        csv_path = self._write_fixture(
            db_session and tmp_path,
            ["MM-1,Peugeot,308,2022,35000,Diesel,VENTE,15000,,2026-06-20"],
        )

        run_migration(csv_path, db_session)
        report_2 = run_migration(csv_path, db_session)

        assert report_2.inserted == 0
        assert report_2.updated == 1
        assert db_session.query(Vehicle).count() == 1

    def test_migration_rejects_duplicate_refs_within_same_file(self, db_session, tmp_path):
        csv_path = self._write_fixture(
            db_session and tmp_path,
            [
                "MM-1,Peugeot,308,2022,35000,Diesel,VENTE,15000,,2026-06-20",
                "MM-1,Peugeot,308,2022,35000,Diesel,VENTE,15000,,2026-06-20",
            ],
        )

        report = run_migration(csv_path, db_session)

        assert report.inserted == 1
        assert report.rejected == 1
        assert db_session.query(Vehicle).count() == 1

    def test_real_legacy_export_file_runs_without_crashing(self, db_session):
        """Sanity check sur le vrai fichier livré (legacy_data/m_motors_legacy_export.csv)."""
        real_file = Path(__file__).parent.parent / "legacy_data" / "m_motors_legacy_export.csv"

        report = run_migration(real_file, db_session)

        assert report.total_rows > 100
        assert report.inserted > 100
        assert report.rejected > 0  # le fichier contient volontairement des défauts
