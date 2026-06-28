from app.core.security import create_access_token, hash_password
from app.models.user import User, UserRole
from app.models.vehicle import Vehicle, VehicleMode, VehicleStatus


def _create_admin(db_session):
    user = User(
        email="admin@example.com",
        full_name="Admin M-Motors",
        hashed_password=hash_password("MotDePasse123"),
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _auth_headers(user):
    token = create_access_token({"sub": user.id, "role": user.role.value})
    return {"Authorization": f"Bearer {token}"}


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
    )
    defaults.update(overrides)
    vehicle = Vehicle(**defaults)
    db_session.add(vehicle)
    db_session.commit()
    db_session.refresh(vehicle)
    return vehicle


class TestToggleVehicleMode:
    """Tests pour PATCH /api/vehicles/{id}/toggle-mode — US-09 / MMOT-16."""

    def test_toggle_sale_to_rental_requires_monthly_price(self, client, db_session):
        admin = _create_admin(db_session)
        vehicle = _make_vehicle(db_session, mode=VehicleMode.SALE, price_eur=15000)

        response = client.patch(
            f"/api/vehicles/{vehicle.id}/toggle-mode",
            json={"monthly_price_eur": 320, "rental_included_services": ["Assurance tous risques"]},
            headers=_auth_headers(admin),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "rental"
        assert body["monthly_price_eur"] == "320.00"
        assert body["rental_included_services"] == "Assurance tous risques"

    def test_toggle_sale_to_rental_without_price_is_rejected(self, client, db_session):
        admin = _create_admin(db_session)
        vehicle = _make_vehicle(db_session, mode=VehicleMode.SALE)

        response = client.patch(
            f"/api/vehicles/{vehicle.id}/toggle-mode", json={}, headers=_auth_headers(admin)
        )

        assert response.status_code == 422

    def test_toggle_rental_to_sale_reuses_existing_price_if_not_provided(self, client, db_session):
        admin = _create_admin(db_session)
        vehicle = _make_vehicle(
            db_session, mode=VehicleMode.RENTAL, price_eur=12000, monthly_price_eur=300
        )

        response = client.patch(
            f"/api/vehicles/{vehicle.id}/toggle-mode", json={}, headers=_auth_headers(admin)
        )

        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "sale"
        assert body["price_eur"] == "12000.00"

    def test_toggle_records_history(self, client, db_session):
        admin = _create_admin(db_session)
        vehicle = _make_vehicle(db_session, mode=VehicleMode.SALE)

        response = client.patch(
            f"/api/vehicles/{vehicle.id}/toggle-mode",
            json={"monthly_price_eur": 300},
            headers=_auth_headers(admin),
        )

        history = response.json()["mode_changes"]
        assert len(history) == 1
        assert history[0]["previous_mode"] == "sale"
        assert history[0]["new_mode"] == "rental"

    def test_toggle_twice_accumulates_history(self, client, db_session):
        admin = _create_admin(db_session)
        vehicle = _make_vehicle(db_session, mode=VehicleMode.SALE)

        client.patch(
            f"/api/vehicles/{vehicle.id}/toggle-mode",
            json={"monthly_price_eur": 300},
            headers=_auth_headers(admin),
        )
        response = client.patch(
            f"/api/vehicles/{vehicle.id}/toggle-mode", json={}, headers=_auth_headers(admin)
        )

        assert len(response.json()["mode_changes"]) == 2

    def test_client_cannot_toggle_mode(self, client, db_session):
        client_user = User(
            email="client@example.com", full_name="Client", hashed_password=hash_password("MotDePasse123")
        )
        db_session.add(client_user)
        db_session.commit()
        vehicle = _make_vehicle(db_session)

        response = client.patch(
            f"/api/vehicles/{vehicle.id}/toggle-mode",
            json={"monthly_price_eur": 300},
            headers=_auth_headers(client_user),
        )

        assert response.status_code == 403

    def test_toggle_unknown_vehicle_returns_404(self, client, db_session):
        admin = _create_admin(db_session)
        response = client.patch(
            "/api/vehicles/does-not-exist/toggle-mode", json={}, headers=_auth_headers(admin)
        )
        assert response.status_code == 404
