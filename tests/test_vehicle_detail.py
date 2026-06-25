from app.models.vehicle import Vehicle, VehicleMode, VehicleStatus


def _make_vehicle(db_session, **overrides):
    defaults = dict(
        brand="Peugeot",
        model="308",
        motorization="Diesel",
        year=2022,
        mileage_km=30000,
        mode=VehicleMode.SALE,
        status=VehicleStatus.AVAILABLE,
        price_eur=15000,
        monthly_price_eur=None,
        rental_included_services=None,
    )
    defaults.update(overrides)
    vehicle = Vehicle(**defaults)
    db_session.add(vehicle)
    db_session.commit()
    db_session.refresh(vehicle)
    return vehicle


class TestVehicleDetail:
    """Tests pour GET /api/vehicles/{id} — US-04 / MMOT-10."""

    def test_get_existing_vehicle_returns_full_details(self, client, db_session):
        vehicle = _make_vehicle(db_session, brand="Peugeot", model="308")

        response = client.get(f"/api/vehicles/{vehicle.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == vehicle.id
        assert body["brand"] == "Peugeot"
        assert body["model"] == "308"
        assert body["price_eur"] == "15000.00"

    def test_get_rental_vehicle_returns_monthly_price(self, client, db_session):
        vehicle = _make_vehicle(
            db_session,
            mode=VehicleMode.RENTAL,
            price_eur=None,
            monthly_price_eur=349,
            rental_included_services="Assurance tous risques,Entretien et SAV",
        )

        response = client.get(f"/api/vehicles/{vehicle.id}")

        body = response.json()
        assert body["mode"] == "rental"
        assert body["monthly_price_eur"] == "349.00"
        assert "Assurance" in body["rental_included_services"]

    def test_get_unknown_vehicle_returns_404(self, client):
        response = client.get("/api/vehicles/does-not-exist")

        assert response.status_code == 404
        assert response.json()["detail"] == "Véhicule introuvable."

    def test_get_sold_vehicle_is_still_viewable_by_id(self, client, db_session):
        # Contrairement à la recherche (US-03), la fiche détaillée reste
        # accessible par lien direct même si le véhicule n'est plus "available"
        # (ex: lien partagé, suivi d'un dossier déjà en cours).
        vehicle = _make_vehicle(db_session, status=VehicleStatus.SOLD)

        response = client.get(f"/api/vehicles/{vehicle.id}")

        assert response.status_code == 200
