from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_profile_requires_email() -> None:
    response = client.get("/profile/demo-user")

    assert response.status_code == 422
    assert response.json() == {"detail": "email is required"}


def test_profile_normalizes_email() -> None:
    response = client.get(
        "/profile/demo-user",
        params={"email": "Demo@Example.com"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "demo-user",
        "email": "demo@example.com",
    }
