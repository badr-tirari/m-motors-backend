from app.core.notifications import EmailNotifier, get_email_notifier
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import User, UserRole
from app.models.vehicle import Vehicle, VehicleMode, VehicleStatus


class CapturingEmailNotifier:
    """Notifieur de test : capture les emails envoyés au lieu de les logger."""

    def __init__(self):
        self.sent: list[dict] = []

    def send(self, to: str, subject: str, body: str) -> bool:
        self.sent.append({"to": to, "subject": subject, "body": body})
        return True


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


class TestDecideDossier:
    """Tests pour PATCH /api/dossiers/{id}/decision — US-11 / MMOT-18."""

    def _create_dossier(self, client, db_session):
        owner = _create_user(db_session)
        vehicle = _make_vehicle(db_session)
        dossier = client.post(
            "/api/dossiers", json={"vehicle_id": vehicle.id}, headers=_auth_headers(owner)
        ).json()
        return owner, dossier["id"]

    def test_approve_dossier_updates_status_and_notifies_client(self, client, db_session):
        notifier = CapturingEmailNotifier()
        app.dependency_overrides[get_email_notifier] = lambda: notifier
        try:
            admin = _create_user(db_session, email="admin@example.com", role=UserRole.ADMIN)
            owner, dossier_id = self._create_dossier(client, db_session)

            response = client.patch(
                f"/api/dossiers/{dossier_id}/decision",
                json={"decision": "approved"},
                headers=_auth_headers(admin),
            )

            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "approved"
            assert len(body["status_events"]) == 2  # pending puis approved
            assert len(notifier.sent) == 1
            assert notifier.sent[0]["to"] == owner.email
            assert "validé" in notifier.sent[0]["subject"]
        finally:
            app.dependency_overrides.pop(get_email_notifier, None)

    def test_reject_dossier_with_reason(self, client, db_session):
        notifier = CapturingEmailNotifier()
        app.dependency_overrides[get_email_notifier] = lambda: notifier
        try:
            admin = _create_user(db_session, email="admin@example.com", role=UserRole.ADMIN)
            owner, dossier_id = self._create_dossier(client, db_session)

            response = client.patch(
                f"/api/dossiers/{dossier_id}/decision",
                json={"decision": "rejected", "reason": "Revenus insuffisants"},
                headers=_auth_headers(admin),
            )

            body = response.json()
            assert body["status"] == "rejected"
            assert body["rejection_reason"] == "Revenus insuffisants"
            assert "Revenus insuffisants" in notifier.sent[0]["body"]
        finally:
            app.dependency_overrides.pop(get_email_notifier, None)

    def test_reject_without_reason_is_allowed(self, client, db_session):
        admin = _create_user(db_session, email="admin@example.com", role=UserRole.ADMIN)
        owner, dossier_id = self._create_dossier(client, db_session)

        response = client.patch(
            f"/api/dossiers/{dossier_id}/decision", json={"decision": "rejected"}, headers=_auth_headers(admin)
        )

        assert response.status_code == 200

    def test_cannot_decide_twice(self, client, db_session):
        admin = _create_user(db_session, email="admin@example.com", role=UserRole.ADMIN)
        owner, dossier_id = self._create_dossier(client, db_session)

        client.patch(f"/api/dossiers/{dossier_id}/decision", json={"decision": "approved"}, headers=_auth_headers(admin))
        response = client.patch(
            f"/api/dossiers/{dossier_id}/decision", json={"decision": "rejected"}, headers=_auth_headers(admin)
        )

        assert response.status_code == 409

    def test_decision_must_not_be_pending(self, client, db_session):
        admin = _create_user(db_session, email="admin@example.com", role=UserRole.ADMIN)
        owner, dossier_id = self._create_dossier(client, db_session)

        response = client.patch(
            f"/api/dossiers/{dossier_id}/decision", json={"decision": "pending"}, headers=_auth_headers(admin)
        )

        assert response.status_code == 422

    def test_client_cannot_decide(self, client, db_session):
        owner, dossier_id = self._create_dossier(client, db_session)

        response = client.patch(
            f"/api/dossiers/{dossier_id}/decision", json={"decision": "approved"}, headers=_auth_headers(owner)
        )

        assert response.status_code == 403

    def test_unknown_dossier_returns_404(self, client, db_session):
        admin = _create_user(db_session, email="admin@example.com", role=UserRole.ADMIN)
        response = client.patch(
            "/api/dossiers/does-not-exist/decision", json={"decision": "approved"}, headers=_auth_headers(admin)
        )
        assert response.status_code == 404
