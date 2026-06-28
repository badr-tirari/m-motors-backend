import io

from app.core.security import create_access_token, hash_password
from app.core.storage import LocalFileStorage, get_file_storage
from app.main import app
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


def _make_vehicle(db_session, mode=VehicleMode.SALE):
    vehicle = Vehicle(
        brand="Peugeot",
        model="308",
        motorization="Diesel",
        year=2022,
        mileage_km=30000,
        mode=mode,
        status=VehicleStatus.AVAILABLE,
        price_eur=15000 if mode == VehicleMode.SALE else None,
        monthly_price_eur=None if mode == VehicleMode.SALE else 300,
    )
    db_session.add(vehicle)
    db_session.commit()
    db_session.refresh(vehicle)
    return vehicle


class TestCreateDossier:
    """Tests pour POST /api/dossiers — US-05 / MMOT-12."""

    def test_create_dossier_returns_pending_status(self, client, db_session):
        user = _create_client(db_session)
        vehicle = _make_vehicle(db_session)

        response = client.post(
            "/api/dossiers", json={"vehicle_id": vehicle.id}, headers=_auth_headers(user)
        )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "pending"
        assert body["type"] == "sale"
        assert len(body["status_events"]) == 1
        assert body["status_events"][0]["status"] == "pending"

    def test_create_dossier_requires_auth(self, client, db_session):
        vehicle = _make_vehicle(db_session)
        response = client.post("/api/dossiers", json={"vehicle_id": vehicle.id})
        assert response.status_code == 401

    def test_create_dossier_unknown_vehicle_returns_404(self, client, db_session):
        user = _create_client(db_session)
        response = client.post(
            "/api/dossiers", json={"vehicle_id": "does-not-exist"}, headers=_auth_headers(user)
        )
        assert response.status_code == 404

    def test_create_dossier_duplicate_pending_is_rejected(self, client, db_session):
        user = _create_client(db_session)
        vehicle = _make_vehicle(db_session)

        client.post("/api/dossiers", json={"vehicle_id": vehicle.id}, headers=_auth_headers(user))
        response = client.post("/api/dossiers", json={"vehicle_id": vehicle.id}, headers=_auth_headers(user))

        assert response.status_code == 409

    def test_create_rental_dossier_has_rental_type(self, client, db_session):
        user = _create_client(db_session)
        vehicle = _make_vehicle(db_session, mode=VehicleMode.RENTAL)

        response = client.post(
            "/api/dossiers", json={"vehicle_id": vehicle.id}, headers=_auth_headers(user)
        )

        assert response.json()["type"] == "rental"


class TestUploadDocument:
    """Tests pour POST /api/dossiers/{id}/documents — US-05 / MMOT-12."""

    def _create_dossier(self, client, db_session, user=None):
        user = user or _create_client(db_session)
        vehicle = _make_vehicle(db_session)
        response = client.post("/api/dossiers", json={"vehicle_id": vehicle.id}, headers=_auth_headers(user))
        return user, response.json()["id"]

    def test_upload_pdf_document_succeeds(self, client, db_session, tmp_path):
        app.dependency_overrides[get_file_storage] = lambda: LocalFileStorage(base_dir=tmp_path)
        try:
            user, dossier_id = self._create_dossier(client, db_session)
            files = {"file": ("piece_identite.pdf", io.BytesIO(b"%PDF-1.4 fake content"), "application/pdf")}

            response = client.post(
                f"/api/dossiers/{dossier_id}/documents", files=files, headers=_auth_headers(user)
            )

            assert response.status_code == 201
            body = response.json()
            assert body["original_filename"] == "piece_identite.pdf"
            assert body["content_type"] == "application/pdf"
        finally:
            app.dependency_overrides.pop(get_file_storage, None)

    def test_upload_rejects_unsupported_content_type(self, client, db_session, tmp_path):
        app.dependency_overrides[get_file_storage] = lambda: LocalFileStorage(base_dir=tmp_path)
        try:
            user, dossier_id = self._create_dossier(client, db_session)
            files = {"file": ("script.exe", io.BytesIO(b"MZ"), "application/x-msdownload")}

            response = client.post(
                f"/api/dossiers/{dossier_id}/documents", files=files, headers=_auth_headers(user)
            )

            assert response.status_code == 422
        finally:
            app.dependency_overrides.pop(get_file_storage, None)

    def test_upload_by_non_owner_is_forbidden(self, client, db_session, tmp_path):
        app.dependency_overrides[get_file_storage] = lambda: LocalFileStorage(base_dir=tmp_path)
        try:
            owner, dossier_id = self._create_dossier(client, db_session)
            other_user = _create_client(db_session, email="autre@example.com")
            files = {"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")}

            response = client.post(
                f"/api/dossiers/{dossier_id}/documents", files=files, headers=_auth_headers(other_user)
            )

            assert response.status_code == 403
        finally:
            app.dependency_overrides.pop(get_file_storage, None)

    def test_upload_to_unknown_dossier_returns_404(self, client, db_session, tmp_path):
        app.dependency_overrides[get_file_storage] = lambda: LocalFileStorage(base_dir=tmp_path)
        try:
            user = _create_client(db_session)
            files = {"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")}

            response = client.post(
                "/api/dossiers/does-not-exist/documents", files=files, headers=_auth_headers(user)
            )

            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_file_storage, None)
