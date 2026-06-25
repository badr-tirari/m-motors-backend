from app.core.security import create_access_token
from app.models.user import User, UserRole


def _create_user(db_session, email="client@example.com", password="MotDePasseSolide123", role=UserRole.CLIENT):
    from app.core.security import hash_password

    user = User(email=email, full_name="Jean Dupont", hashed_password=hash_password(password), role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestLogin:
    """Tests pour POST /api/auth/login — US-02 / MMOT-8."""

    def test_login_success_returns_token(self, client, db_session):
        _create_user(db_session)

        response = client.post(
            "/api/auth/login",
            json={"email": "client@example.com", "password": "MotDePasseSolide123"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert len(body["access_token"]) > 20

    def test_login_wrong_password_returns_401(self, client, db_session):
        _create_user(db_session)

        response = client.post(
            "/api/auth/login",
            json={"email": "client@example.com", "password": "MauvaisMotDePasse"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Email ou mot de passe incorrect."

    def test_login_unknown_email_returns_401(self, client):
        response = client.post(
            "/api/auth/login",
            json={"email": "inconnu@example.com", "password": "MotDePasseSolide123"},
        )

        assert response.status_code == 401


class TestMe:
    """Tests pour GET /api/auth/me — vérifie le décodage JWT et le rôle."""

    def test_me_with_valid_token_returns_user(self, client, db_session):
        user = _create_user(db_session)
        token = create_access_token({"sub": user.id, "role": user.role.value})

        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.json()["email"] == user.email

    def test_me_without_token_returns_401(self, client):
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_me_with_invalid_token_returns_401(self, client):
        response = client.get("/api/auth/me", headers={"Authorization": "Bearer token-invalide"})
        assert response.status_code == 401


class TestRoleGuard:
    """Tests pour la garde require_admin (US-02 — gestion des rôles)."""

    def test_admin_check_rejects_client_role(self, client, db_session):
        user = _create_user(db_session, email="client2@example.com", role=UserRole.CLIENT)
        token = create_access_token({"sub": user.id, "role": user.role.value})

        response = client.get("/api/auth/admin-check", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 403

    def test_admin_check_accepts_admin_role(self, client, db_session):
        admin = _create_user(db_session, email="admin@example.com", role=UserRole.ADMIN)
        token = create_access_token({"sub": admin.id, "role": admin.role.value})

        response = client.get("/api/auth/admin-check", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert "admin@example.com" in response.json()["message"]
