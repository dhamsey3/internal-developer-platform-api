from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.admin import upsert_admin
from auth.jwt_utils import verify_password
from database.models import Base, User


def test_upsert_admin_creates_and_updates_admin(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr("app.admin.SessionLocal", test_session)

    passwords = iter(["first-password", "first-password", "second-password", "second-password"])
    monkeypatch.setattr("getpass.getpass", lambda prompt: next(passwords))

    upsert_admin("cli-admin")
    upsert_admin("cli-admin")

    db = test_session()
    try:
        user = db.query(User).filter(User.username == "cli-admin").one()
        assert user.role == "admin"
        assert verify_password("second-password", user.hashed_password)
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
