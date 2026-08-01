from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.models import Base, Deployment
from services.sandbox_sweeper import sweep_expired_sandboxes


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine)()


def _sandbox(status: str, expires_at: datetime, deployment_id: Optional[int] = None) -> Deployment:
    deployment = Deployment(
        owner_id=0,
        name="sandbox-whoami",
        namespace="sandbox",
        image="mpepping/whoami:latest",
        port=20001,
        container_port=8000,
        replicas=1,
        is_sandbox=True,
        status=status,
        expires_at=expires_at,
        metadata_json={},
    )
    if deployment_id is not None:
        deployment.id = deployment_id
    return deployment


def test_sweeper_expires_stale_sandbox_and_removes_container(monkeypatch):
    engine, db = _session()
    now = datetime.now(timezone.utc)
    run = MagicMock()
    monkeypatch.setattr("services.sandbox_sweeper.subprocess.run", run)
    try:
        deployment = _sandbox("running", now - timedelta(minutes=1), deployment_id=7)
        db.add(deployment)
        db.commit()

        count = sweep_expired_sandboxes(db, now=now)
        db.refresh(deployment)

        assert count == 1
        assert deployment.status == "expired"
        assert "swept_at" in deployment.metadata_json
        run.assert_any_call(
            ["docker", "rm", "-f", "7"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_sweeper_ignores_unexpired_sandbox(monkeypatch):
    engine, db = _session()
    now = datetime.now(timezone.utc)
    run = MagicMock()
    monkeypatch.setattr("services.sandbox_sweeper.subprocess.run", run)
    try:
        deployment = _sandbox("running", now + timedelta(minutes=1))
        db.add(deployment)
        db.commit()

        count = sweep_expired_sandboxes(db, now=now)
        db.refresh(deployment)

        assert count == 0
        assert deployment.status == "running"
        run.assert_not_called()
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_missing_docker_does_not_break_sweeper(monkeypatch):
    engine, db = _session()
    now = datetime.now(timezone.utc)
    run = MagicMock(side_effect=FileNotFoundError)
    monkeypatch.setattr("services.sandbox_sweeper.subprocess.run", run)
    try:
        deployment = _sandbox("queued", now - timedelta(minutes=1))
        db.add(deployment)
        db.commit()

        count = sweep_expired_sandboxes(db, now=now)
        db.refresh(deployment)

        assert count == 1
        assert deployment.status == "expired"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
