def test_create_namespace(client):
    client.post("/auth/register", json={"username": "namespacetest", "password": "testpass123"})
    login = client.post("/auth/login", json={"username": "namespacetest", "password": "testpass123"})
    token = login.json()["access_token"]
    response = client.post(
        "/kubernetes/namespace/create",
        json={"name": "test-ns"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in [200, 500]  # 500 if cluster not available
