from app.core.security import create_access_token, hash_password
from app.models.user import User, UserRole
from app.models.vehicle import Vehicle


def _create_user(db_session, email="user@example.com", role=UserRole.CLIENT):
    user = User(email=email, full_name="Test User", hashed_password=hash_password("MotDePasse123"), role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _auth_headers(user):
    token = create_access_token({"sub": user.id, "role": user.role.value})
    return {"Authorization": f"Bearer {token}"}


VALID_SALE_PAYLOAD = {
    "brand": "Peugeot",
    "model": "308",
    "motorization": "Diesel",
    "year": 2023,
    "mileage_km": 12000,
    "mode": "sale",
    "price_eur": 18000,
}


class TestCreateVehicleSale:
    """Tests pour POST /api/vehicles (mode vente) — US-07 / MMOT-14."""

    def test_admin_can_create_sale_vehicle(self, client, db_session):
        admin = _create_user(db_session, email="admin@example.com", role=UserRole.ADMIN)

        response = client.post("/api/vehicles", json=VALID_SALE_PAYLOAD, headers=_auth_headers(admin))

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "available"
        assert body["mode"] == "sale"
        assert body["price_eur"] == "18000.00"

        assert db_session.query(Vehicle).count() == 1

    def test_client_cannot_create_vehicle(self, client, db_session):
        client_user = _create_user(db_session)

        response = client.post("/api/vehicles", json=VALID_SALE_PAYLOAD, headers=_auth_headers(client_user))

        assert response.status_code == 403

    def test_requires_auth(self, client):
        response = client.post("/api/vehicles", json=VALID_SALE_PAYLOAD)
        assert response.status_code == 401

    def test_sale_without_price_is_rejected(self, client, db_session):
        admin = _create_user(db_session, email="admin@example.com", role=UserRole.ADMIN)
        payload = {**VALID_SALE_PAYLOAD, "price_eur": None}

        response = client.post("/api/vehicles", json=payload, headers=_auth_headers(admin))

        assert response.status_code == 422

    def test_created_vehicle_is_immediately_searchable(self, client, db_session):
        admin = _create_user(db_session, email="admin@example.com", role=UserRole.ADMIN)
        client.post("/api/vehicles", json=VALID_SALE_PAYLOAD, headers=_auth_headers(admin))

        response = client.get("/api/vehicles", params={"brand": "Peugeot"})

        assert response.json()["total"] == 1
