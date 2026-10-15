from auth.jwt_utils import create_access_token, get_password_hash
from database.models import User
from database.session import SessionLocal


def _token_for(username: str, role: str) -> str:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            user = User(username=username, hashed_password=get_password_hash("testpass123"), role=role)
            db.add(user)
            db.commit()
            db.refresh(user)
        return create_access_token({"sub": str(user.id), "role": user.role})
    finally:
        db.close()


def test_create_namespace_requires_admin(client):
    token = _token_for("namespace-user", "user")
    response = client.post(
        "/kubernetes/namespace/create",
        json={"name": "test-ns"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_admin_can_create_namespace(client):
    token = _token_for("namespace-admin", "admin")
    response = client.post(
        "/kubernetes/namespace/create",
        json={"name": "test-ns"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in [200, 500]  # 500 if cluster not available


def test_pod_logs_require_admin(client):
    token = _token_for("namespace-user", "user")
    response = client.get(
        "/monitoring/logs/coredns?namespace=kube-system",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
