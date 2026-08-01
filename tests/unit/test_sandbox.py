from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.routes.deployments import patch_deployment_status
from api.schemas import DeploymentStatusPatch
from database.models import Base, Deployment
from services.sandbox_service import SANDBOX_TTL_SECONDS
from services.sandbox_service import create_sandbox_deployment, dispatch_sandbox_deployment


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine)()


def test_sandbox_demo_uses_allowlisted_template():
    engine, db = _session()
    try:
        deployment = create_sandbox_deployment(db, "whoami")

        assert deployment.is_sandbox is True
        assert deployment.status == "queued"
        assert deployment.image == "mpepping/whoami:latest"
        assert deployment.container_port == 8000
        assert deployment.port == 20000 + deployment.id
        assert deployment.expires_at is not None
        assert deployment.metadata_json["ttl_seconds"] == SANDBOX_TTL_SECONDS
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_sandbox_rejects_arbitrary_template():
    engine, db = _session()
    try:
        try:
            create_sandbox_deployment(db, "ghcr-io-user-app")
        except ValueError as exc:
            assert str(exc) == "Unsupported sandbox template"
        else:
            raise AssertionError("Expected arbitrary sandbox template to be rejected")
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_sandbox_dispatch_sends_repository_dispatch_payload(monkeypatch):
    deployment = Deployment(
        id=9,
        owner_id=0,
        name="sandbox-whoami-9",
        namespace="sandbox",
        image="mpepping/whoami:latest",
        port=20009,
        container_port=8000,
        replicas=1,
        is_sandbox=True,
        status="queued",
    )
    response = SimpleNamespace(status_code=204)
    post = MagicMock(return_value=response)
    monkeypatch.setattr("services.sandbox_service.httpx.post", post)
    monkeypatch.setattr("services.sandbox_service.settings.GITHUB_DISPATCH_TOKEN", "token")
    monkeypatch.setattr("services.sandbox_service.settings.GITHUB_REPOSITORY", "example/platform")

    dispatch_sandbox_deployment(deployment)

    request = post.call_args.kwargs
    assert request["json"]["event_type"] == "deploy_sandbox"
    assert request["json"]["client_payload"]["deployment_id"] == "9"
    assert request["json"]["client_payload"]["image"] == "mpepping/whoami:latest"
    assert request["json"]["client_payload"]["host_port"] == "20009"
    assert "token" not in request["json"]["client_payload"]


def test_sandbox_status_patch_requires_callback_token(monkeypatch):
    engine, db = _session()
    monkeypatch.setattr("api.routes.deployments.settings.DEPLOYMENT_CALLBACK_TOKEN", "callback-token")
    try:
        deployment = create_sandbox_deployment(db, "whoami")

        try:
            patch_deployment_status(
                deployment.id,
                DeploymentStatusPatch(status="running"),
                "wrong-token",
                db,
            )
        except Exception as exc:
            assert getattr(exc, "status_code") == 401
        else:
            raise AssertionError("Expected invalid callback token to be rejected")
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_sandbox_status_patch_updates_runtime_details(monkeypatch):
    engine, db = _session()
    monkeypatch.setattr("api.routes.deployments.settings.DEPLOYMENT_CALLBACK_TOKEN", "callback-token")
    try:
        deployment = create_sandbox_deployment(db, "whoami")

        updated = patch_deployment_status(
            deployment.id,
            DeploymentStatusPatch(
                status="running",
                url="http://example.test:20001",
                host_port=20001,
                runtime_id="container-123",
                logs="ready",
            ),
            "callback-token",
            db,
        )

        assert updated.status == "running"
        assert updated.url == "http://example.test:20001"
        assert updated.port == 20001
        assert updated.metadata_json["runtime_id"] == "container-123"
        assert updated.metadata_json["logs"] == "ready"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
