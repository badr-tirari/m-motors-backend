from app.core.security import verify_password
from app.models.user import User


class TestRegister:
    """Tests pour POST /api/auth/register — US-01 / MMOT-7."""

    VALID_PAYLOAD = {
        "email": "client@example.com",
        "full_name": "Jean Dupont",
        "password": "MotDePasseSolide123",
    }

    def test_register_success_returns_201_and_user(self, client):
        response = client.post("/api/auth/register", json=self.VALID_PAYLOAD)

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == self.VALID_PAYLOAD["email"]
        assert body["full_name"] == self.VALID_PAYLOAD["full_name"]
        assert body["role"] == "client"
        assert "id" in body
        # Le mot de passe ne doit jamais apparaître dans la réponse.
        assert "password" not in body
        assert "hashed_password" not in body

    def test_register_persists_user_with_hashed_password(self, client, db_session):
        client.post("/api/auth/register", json=self.VALID_PAYLOAD)

        user = db_session.query(User).filter_by(email=self.VALID_PAYLOAD["email"]).first()
        assert user is not None
        assert user.hashed_password != self.VALID_PAYLOAD["password"]
        assert verify_password(self.VALID_PAYLOAD["password"], user.hashed_password)

    def test_register_duplicate_email_returns_409(self, client):
        client.post("/api/auth/register", json=self.VALID_PAYLOAD)
        response = client.post("/api/auth/register", json=self.VALID_PAYLOAD)

        assert response.status_code == 409
        assert "existe déjà" in response.json()["detail"]

    def test_register_invalid_email_returns_422(self, client):
        payload = {**self.VALID_PAYLOAD, "email": "pas-un-email"}
        response = client.post("/api/auth/register", json=payload)

        assert response.status_code == 422

    def test_register_password_too_short_returns_422(self, client):
        payload = {**self.VALID_PAYLOAD, "email": "autre@example.com", "password": "court1"}
        response = client.post("/api/auth/register", json=payload)

        assert response.status_code == 422

    def test_register_missing_full_name_returns_422(self, client):
        payload = {"email": "x@example.com", "password": "MotDePasseSolide123"}
        response = client.post("/api/auth/register", json=payload)

        assert response.status_code == 422
