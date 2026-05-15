def test_register(client):
    response = client.post("/auth/register", json={"username": "testuser", "password": "testpass123"})
    if response.status_code == 400:
        assert response.json()["detail"] == "Username already registered"
        return
    assert response.status_code == 200

def test_login(client):
    client.post("/auth/register", json={"username": "testuser", "password": "testpass123"})
    response = client.post("/auth/login", json={"username": "testuser", "password": "testpass123"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_register_rejects_invalid_username(client):
    response = client.post("/auth/register", json={"username": "../bad", "password": "testpass123"})
    assert response.status_code == 422
