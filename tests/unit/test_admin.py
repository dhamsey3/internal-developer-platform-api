from app.admin import upsert_admin
from auth.jwt_utils import verify_password
from database.models import User
from database.session import SessionLocal


def test_upsert_admin_creates_and_updates_admin(monkeypatch):
    passwords = iter(["first-password", "first-password", "second-password", "second-password"])
    monkeypatch.setattr("getpass.getpass", lambda prompt: next(passwords))

    upsert_admin("cli-admin")
    upsert_admin("cli-admin")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "cli-admin").one()
        assert user.role == "admin"
        assert verify_password("second-password", user.hashed_password)
        db.delete(user)
        db.commit()
    finally:
        db.close()
