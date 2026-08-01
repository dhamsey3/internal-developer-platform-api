from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.routes.deployments import patch_deployment_status
from api.schemas import DeploymentStatusPatch
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


def _deployment(db, status="queued", expires_at=None):
    deployment = Deployment(
        owner_id=0,
        name="sandbox-whoami-42",
        namespace="sandbox",
        image="mpepping/whoami:latest",
        port=20042,
        container_port=8000,
        replicas=1,
        status=status,
        is_sandbox=True,
        expires_at=expires_at or datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    return deployment


def test_valid_sandbox_lifecycle_queued_running_expired(monkeypatch):
    engine, db = _session()
    monkeypatch.setattr("api.routes.deployments.settings.DEPLOYMENT_CALLBACK_TOKEN", "callback-token")
    monkeypatch.setattr("services.sandbox_sweeper.subprocess.run", lambda *args, **kwargs: None)
    try:
        deployment = _deployment(db, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))

        running = patch_deployment_status(
            deployment.id,
            DeploymentStatusPatch(status="running", host_port=20042, container_port=8000),
            "callback-token",
            db,
        )
        assert running.status == "running"
        assert running.container_port == 8000

        assert sweep_expired_sandboxes(db) == 1
        db.refresh(deployment)
        assert deployment.status == "expired"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_terminal_sandbox_state_cannot_be_overwritten(monkeypatch):
    engine, db = _session()
    monkeypatch.setattr("api.routes.deployments.settings.DEPLOYMENT_CALLBACK_TOKEN", "callback-token")
    try:
        deployment = _deployment(db, status="expired")

        try:
            patch_deployment_status(
                deployment.id,
                DeploymentStatusPatch(status="running"),
                "callback-token",
                db,
            )
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("Expected expired deployment to reject running callback")
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_reentrant_sandbox_callback_is_idempotent(monkeypatch):
    engine, db = _session()
    monkeypatch.setattr("api.routes.deployments.settings.DEPLOYMENT_CALLBACK_TOKEN", "callback-token")
    try:
        deployment = _deployment(db, status="running")

        same = patch_deployment_status(
            deployment.id,
            DeploymentStatusPatch(status="running"),
            "callback-token",
            db,
        )

        assert same.id == deployment.id
        assert same.status == "running"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_sandbox_callback_rejects_missing_and_invalid_tokens(monkeypatch):
    engine, db = _session()
    monkeypatch.setattr("api.routes.deployments.settings.DEPLOYMENT_CALLBACK_TOKEN", "callback-token")
    try:
        deployment = _deployment(db)

        for token in ("", "wrong-token"):
            try:
                patch_deployment_status(
                    deployment.id,
                    DeploymentStatusPatch(status="running"),
                    token,
                    db,
                )
            except HTTPException as exc:
                assert exc.status_code == 401
            else:
                raise AssertionError("Expected invalid callback token to be rejected")
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
