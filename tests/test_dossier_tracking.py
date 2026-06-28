from app.core.security import create_access_token, hash_password
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleMode, VehicleStatus


def _create_client(db_session, email="client@example.com"):
    user = User(email=email, full_name="Jean Dupont", hashed_password=hash_password("MotDePasse123"))
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


class TestListMyDossiers:
    """Tests pour GET /api/dossiers/me — US-06 / MMOT-13."""

    def test_lists_only_current_user_dossiers_most_recent_first(self, client, db_session):
        user = _create_client(db_session)
        other_user = _create_client(db_session, email="autre@example.com")
        vehicle_a = _make_vehicle(db_session, brand="Peugeot")
        vehicle_b = _make_vehicle(db_session, brand="Renault")

        client.post("/api/dossiers", json={"vehicle_id": vehicle_a.id}, headers=_auth_headers(user))
        client.post("/api/dossiers", json={"vehicle_id": vehicle_b.id}, headers=_auth_headers(user))
        client.post("/api/dossiers", json={"vehicle_id": vehicle_a.id}, headers=_auth_headers(other_user))

        response = client.get("/api/dossiers/me", headers=_auth_headers(user))

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert {d["vehicle_id"] for d in body} == {vehicle_a.id, vehicle_b.id}

    def test_requires_auth(self, client):
        response = client.get("/api/dossiers/me")
        assert response.status_code == 401

    def test_empty_list_when_no_dossiers(self, client, db_session):
        user = _create_client(db_session)
        response = client.get("/api/dossiers/me", headers=_auth_headers(user))
        assert response.json() == []


class TestGetDossierDetail:
    """Tests pour GET /api/dossiers/{id} — US-06 / MMOT-13."""

    def test_owner_sees_status_history(self, client, db_session):
        user = _create_client(db_session)
        vehicle = _make_vehicle(db_session)
        created = client.post(
            "/api/dossiers", json={"vehicle_id": vehicle.id}, headers=_auth_headers(user)
        ).json()

        response = client.get(f"/api/dossiers/{created['id']}", headers=_auth_headers(user))

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "pending"
        assert len(body["status_events"]) == 1
        assert body["status_events"][0]["status"] == "pending"

    def test_non_owner_gets_403(self, client, db_session):
        owner = _create_client(db_session)
        other_user = _create_client(db_session, email="autre@example.com")
        vehicle = _make_vehicle(db_session)
        created = client.post(
            "/api/dossiers", json={"vehicle_id": vehicle.id}, headers=_auth_headers(owner)
        ).json()

        response = client.get(f"/api/dossiers/{created['id']}", headers=_auth_headers(other_user))

        assert response.status_code == 403

    def test_unknown_dossier_returns_404(self, client, db_session):
        user = _create_client(db_session)
        response = client.get("/api/dossiers/does-not-exist", headers=_auth_headers(user))
        assert response.status_code == 404
