from app.core.security import create_access_token, hash_password
from app.models.user import User, UserRole


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


VALID_RENTAL_PAYLOAD = {
    "brand": "Renault",
    "model": "Captur",
    "motorization": "Essence",
    "year": 2024,
    "mileage_km": 500,
    "mode": "rental",
    "monthly_price_eur": 349,
    "rental_included_services": ["Assurance tous risques", "Entretien et SAV", "Contrôle technique"],
}


class TestCreateVehicleRental:
    """Tests pour POST /api/vehicles (mode location) — US-08 / MMOT-15."""

    def test_admin_can_create_rental_vehicle_with_services_list(self, client, db_session):
        admin = _create_admin(db_session)

        response = client.post("/api/vehicles", json=VALID_RENTAL_PAYLOAD, headers=_auth_headers(admin))

        assert response.status_code == 201
        body = response.json()
        assert body["mode"] == "rental"
        assert body["monthly_price_eur"] == "349.00"
        assert body["rental_included_services"] == "Assurance tous risques, Entretien et SAV, Contrôle technique"

    def test_rental_accepts_raw_string_for_backward_compatibility(self, client, db_session):
        admin = _create_admin(db_session)
        payload = {**VALID_RENTAL_PAYLOAD, "rental_included_services": "Assurance tous risques"}

        response = client.post("/api/vehicles", json=payload, headers=_auth_headers(admin))

        assert response.json()["rental_included_services"] == "Assurance tous risques"

    def test_rental_without_monthly_price_is_rejected(self, client, db_session):
        admin = _create_admin(db_session)
        payload = {**VALID_RENTAL_PAYLOAD, "monthly_price_eur": None}

        response = client.post("/api/vehicles", json=payload, headers=_auth_headers(admin))

        assert response.status_code == 422

    def test_blank_entries_in_services_list_are_filtered(self, client, db_session):
        admin = _create_admin(db_session)
        payload = {**VALID_RENTAL_PAYLOAD, "rental_included_services": ["Assurance tous risques", "  ", ""]}

        response = client.post("/api/vehicles", json=payload, headers=_auth_headers(admin))

        assert response.json()["rental_included_services"] == "Assurance tous risques"

    def test_created_rental_vehicle_is_searchable_by_mode(self, client, db_session):
        admin = _create_admin(db_session)
        client.post("/api/vehicles", json=VALID_RENTAL_PAYLOAD, headers=_auth_headers(admin))

        response = client.get("/api/vehicles", params={"mode": "rental"})

        assert response.json()["total"] == 1
