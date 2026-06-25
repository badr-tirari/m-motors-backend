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


class TestVehicleSearch:
    """Tests pour GET /api/vehicles — US-03 / MMOT-9."""

    def test_search_without_filters_returns_available_vehicles(self, client, db_session):
        _make_vehicle(db_session, brand="Peugeot")
        _make_vehicle(db_session, brand="Renault")
        _make_vehicle(db_session, brand="Citroën", status=VehicleStatus.SOLD)

        response = client.get("/api/vehicles")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2  # le véhicule vendu est exclu
        brands = {item["brand"] for item in body["items"]}
        assert brands == {"Peugeot", "Renault"}

    def test_filter_by_mode(self, client, db_session):
        _make_vehicle(db_session, mode=VehicleMode.SALE, brand="Peugeot")
        _make_vehicle(
            db_session,
            mode=VehicleMode.RENTAL,
            brand="Renault",
            price_eur=None,
            monthly_price_eur=349,
        )

        response = client.get("/api/vehicles", params={"mode": "rental"})

        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["brand"] == "Renault"

    def test_filter_by_brand_is_partial_and_case_insensitive(self, client, db_session):
        _make_vehicle(db_session, brand="Peugeot")
        _make_vehicle(db_session, brand="Renault")

        response = client.get("/api/vehicles", params={"brand": "peuge"})

        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["brand"] == "Peugeot"

    def test_filter_by_price_range(self, client, db_session):
        _make_vehicle(db_session, brand="Citadine", price_eur=8000)
        _make_vehicle(db_session, brand="Berline", price_eur=22000)

        response = client.get("/api/vehicles", params={"price_min": 10000, "price_max": 30000})

        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["brand"] == "Berline"

    def test_filter_by_mileage_max(self, client, db_session):
        _make_vehicle(db_session, brand="PetitKm", mileage_km=5000)
        _make_vehicle(db_session, brand="GrandKm", mileage_km=150000)

        response = client.get("/api/vehicles", params={"mileage_max": 50000})

        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["brand"] == "PetitKm"

    def test_combined_filters(self, client, db_session):
        _make_vehicle(db_session, brand="Peugeot", mode=VehicleMode.SALE, price_eur=12000, mileage_km=40000)
        _make_vehicle(db_session, brand="Peugeot", mode=VehicleMode.RENTAL, monthly_price_eur=300, price_eur=None)
        _make_vehicle(db_session, brand="Renault", mode=VehicleMode.SALE, price_eur=12000, mileage_km=40000)

        response = client.get(
            "/api/vehicles",
            params={"mode": "sale", "brand": "peugeot", "price_max": 15000, "mileage_max": 60000},
        )

        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["brand"] == "Peugeot"
        assert body["items"][0]["mode"] == "sale"

    def test_pagination(self, client, db_session):
        for i in range(5):
            _make_vehicle(db_session, brand=f"Marque{i}")

        response = client.get("/api/vehicles", params={"page": 2, "page_size": 2})

        body = response.json()
        assert body["total"] == 5
        assert body["page"] == 2
        assert body["page_size"] == 2
        assert len(body["items"]) == 2

    def test_page_size_above_max_is_rejected(self, client):
        response = client.get("/api/vehicles", params={"page_size": 999})
        assert response.status_code == 422
