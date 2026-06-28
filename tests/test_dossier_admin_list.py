import io

from app.core.security import create_access_token, hash_password
from app.core.storage import LocalFileStorage, get_file_storage
from app.main import app
from app.models.user import User, UserRole
from app.models.vehicle import Vehicle, VehicleMode, VehicleStatus


def _create_user(db_session, email="client@example.com", role=UserRole.CLIENT):
    user = User(email=email, full_name="Test User", hashed_password=hash_password("MotDePasse123"), role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _auth_headers(user):
    token = create_access_token({"sub": user.id, "role": user.role.value})
    return {"Authorization": f"Bearer {token}"}


def _make_vehicle(db_session):
    vehicle = Vehicle(
        brand="Peugeot",
        model="308",
        motorization="Diesel",
        year=2022,
        mileage_km=30000,
        mode=VehicleMode.SALE,
        status=VehicleStatus.AVAILABLE,
        price_eur=15000,
    )
    db_session.add(vehicle)
    db_session.commit()
    db_session.refresh(vehicle)
    return vehicle


class TestListDossiersAdmin:
    """Tests pour GET /api/dossiers/admin — US-10 / MMOT-17."""

    def test_admin_sees_all_dossiers_from_every_client(self, client, db_session):
        admin = _create_user(db_session, email="admin@example.com", role=UserRole.ADMIN)
        client_a = _create_user(db_session, email="a@example.com")
        client_b = _create_user(db_session, email="b@example.com")
        vehicle = _make_vehicle(db_session)

        client.post("/api/dossiers", json={"vehicle_id": vehicle.id}, headers=_auth_headers(client_a))
        client.post("/api/dossiers", json={"vehicle_id": vehicle.id}, headers=_auth_headers(client_b))

        response = client.get("/api/dossiers/admin", headers=_auth_headers(admin))

        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_filter_by_status(self, client, db_session):
        admin = _create_user(db_session, email="admin@example.com", role=UserRole.ADMIN)
        client_a = _create_user(db_session, email="a@example.com")
        vehicle = _make_vehicle(db_session)
        client.post("/api/dossiers", json={"vehicle_id": vehicle.id}, headers=_auth_headers(client_a))

        response = client.get("/api/dossiers/admin", params={"status": "approved"}, headers=_auth_headers(admin))

        assert response.json() == []

    def test_client_cannot_access_admin_listing(self, client, db_session):
        client_user = _create_user(db_session)
        response = client.get("/api/dossiers/admin", headers=_auth_headers(client_user))
        assert response.status_code == 403


class TestDownloadDocument:
    """Tests pour GET /api/dossiers/{id}/documents/{doc_id} — US-10 / MMOT-17."""

    def _create_dossier_with_document(self, client, db_session, tmp_path, owner=None):
        owner = owner or _create_user(db_session)
        vehicle = _make_vehicle(db_session)
        dossier = client.post(
            "/api/dossiers", json={"vehicle_id": vehicle.id}, headers=_auth_headers(owner)
        ).json()

        app.dependency_overrides[get_file_storage] = lambda: LocalFileStorage(base_dir=tmp_path)
        files = {"file": ("piece.pdf", io.BytesIO(b"%PDF-1.4 content"), "application/pdf")}
        doc = client.post(
            f"/api/dossiers/{dossier['id']}/documents", files=files, headers=_auth_headers(owner)
        ).json()
        return owner, dossier["id"], doc["id"]

    def test_owner_can_download_own_document(self, client, db_session, tmp_path):
        try:
            owner, dossier_id, doc_id = self._create_dossier_with_document(client, db_session, tmp_path)
            response = client.get(f"/api/dossiers/{dossier_id}/documents/{doc_id}", headers=_auth_headers(owner))
            assert response.status_code == 200
            assert response.content == b"%PDF-1.4 content"
        finally:
            app.dependency_overrides.pop(get_file_storage, None)

    def test_admin_can_download_any_document(self, client, db_session, tmp_path):
        try:
            owner, dossier_id, doc_id = self._create_dossier_with_document(client, db_session, tmp_path)
            admin = _create_user(db_session, email="admin@example.com", role=UserRole.ADMIN)

            response = client.get(f"/api/dossiers/{dossier_id}/documents/{doc_id}", headers=_auth_headers(admin))
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_file_storage, None)

    def test_other_client_cannot_download(self, client, db_session, tmp_path):
        try:
            owner, dossier_id, doc_id = self._create_dossier_with_document(client, db_session, tmp_path)
            stranger = _create_user(db_session, email="stranger@example.com")

            response = client.get(
                f"/api/dossiers/{dossier_id}/documents/{doc_id}", headers=_auth_headers(stranger)
            )
            assert response.status_code == 403
        finally:
            app.dependency_overrides.pop(get_file_storage, None)

    def test_unknown_document_returns_404(self, client, db_session):
        owner = _create_user(db_session)
        vehicle = _make_vehicle(db_session)
        dossier = client.post(
            "/api/dossiers", json={"vehicle_id": vehicle.id}, headers=_auth_headers(owner)
        ).json()

        response = client.get(
            f"/api/dossiers/{dossier['id']}/documents/does-not-exist", headers=_auth_headers(owner)
        )
        assert response.status_code == 404
