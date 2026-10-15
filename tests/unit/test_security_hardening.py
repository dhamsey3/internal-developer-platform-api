from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.routes.applications import deploy_application_route
from api.routes.sandbox import create_sandbox_demo
from api.schemas import ApplicationCreateRequest
from app.config import DEFAULT_SECRET_KEY, Settings
from database.models import Application, Base, Deployment, Destination, User
from services.application_service import create_application
from services.catalog import ImageNotAllowedError, ensure_image_allowed
from services.providers.vm_docker import VMRunnerProvider
from services.sandbox_service import SandboxCapacityError, create_sandbox_deployment
from services.sandbox_sweeper import sweep_expired_sandboxes

STRONG_KEY = "k" * 40


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _settings(**overrides):
    return Settings(_env_file=None, **overrides)


# --- SECRET_KEY: never sign tokens with a key published in this repository ---


@pytest.mark.parametrize("placeholder", ["", DEFAULT_SECRET_KEY, "replace-with-a-long-random-secret"])
def test_production_refuses_missing_or_placeholder_secret_key(placeholder):
    with pytest.raises(ValidationError):
        _settings(ENVIRONMENT="production", SECRET_KEY=placeholder)


def test_production_refuses_unset_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        _settings(ENVIRONMENT="production")


def test_production_refuses_short_secret_key():
    with pytest.raises(ValidationError):
        _settings(ENVIRONMENT="production", SECRET_KEY="too-short")


def test_production_accepts_strong_secret_key():
    assert _settings(ENVIRONMENT="production", SECRET_KEY=STRONG_KEY).SECRET_KEY == STRONG_KEY


@pytest.mark.parametrize("placeholder", ["", DEFAULT_SECRET_KEY, "replace-with-a-long-random-secret"])
def test_local_replaces_placeholder_secret_key_with_random_one(placeholder):
    first = _settings(ENVIRONMENT="local", SECRET_KEY=placeholder).SECRET_KEY
    second = _settings(ENVIRONMENT="local", SECRET_KEY=placeholder).SECRET_KEY
    assert first != placeholder
    assert len(first) >= 32
    assert first != second


# --- Registration is opt-in ---


def test_public_registration_is_off_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_PUBLIC_REGISTRATION", raising=False)
    assert _settings().ENABLE_PUBLIC_REGISTRATION is False


def test_register_is_rejected_when_registration_is_disabled(client, monkeypatch):
    monkeypatch.setattr("api.routes.auth.settings.ENABLE_PUBLIC_REGISTRATION", False)
    response = client.post("/auth/register", json={"username": "latecomer", "password": "testpass123"})
    assert response.status_code == 403


# --- Image policy: only admins deploy images outside the catalog ---


def test_regular_user_may_deploy_catalog_images():
    ensure_image_allowed(SimpleNamespace(role="user"), "nginx:1.25-alpine")


def test_regular_user_may_not_deploy_custom_images():
    with pytest.raises(ImageNotAllowedError):
        ensure_image_allowed(SimpleNamespace(role="user"), "ghcr.io/someone/miner:latest")


def test_admin_may_deploy_custom_images():
    ensure_image_allowed(SimpleNamespace(role="admin"), "ghcr.io/example/orders-api:1.0.0")


def _home_vm(db):
    destination = Destination(
        name="home-vm",
        kind="linux_docker",
        provider="existing_server",
        environment="development",
        config={"enabled": True, "runner_label": "idp-vm", "deployment_workflow": True},
        capabilities=["containers"],
    )
    db.add(destination)
    db.commit()
    db.refresh(destination)
    return destination


def _user(db, role):
    user = User(username=f"{role}-user", hashed_password="not-used", role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_regular_user_cannot_register_application_with_custom_image(db):
    destination = _home_vm(db)
    request = ApplicationCreateRequest(
        name="miner",
        source_type="container_image",
        image="ghcr.io/someone/miner:latest",
        port=8080,
        destination_id=destination.id,
    )
    with pytest.raises(ImageNotAllowedError):
        create_application(db, _user(db, "user"), request)
    assert db.query(Application).count() == 0


def test_deploy_rechecks_image_policy_for_existing_applications(db, monkeypatch):
    # An application registered before the policy existed must not deploy either.
    destination = _home_vm(db)
    user = _user(db, "user")
    application = Application(
        owner_id=user.id,
        destination_id=destination.id,
        name="legacy-app",
        source_type="container_image",
        image="ghcr.io/someone/miner:latest",
        port=8080,
        status="ready_to_deploy",
        metadata_json={},
    )
    db.add(application)
    db.commit()
    dispatch = MagicMock()
    monkeypatch.setattr("api.routes.applications.dispatch_application_deployment", dispatch)

    with pytest.raises(HTTPException) as raised:
        deploy_application_route(application.id, db=db, current_user=user)

    assert raised.value.status_code == 403
    dispatch.assert_not_called()


# --- Sandboxes: capped, and actually removed when they expire ---


def test_sandboxes_are_capped(db, monkeypatch):
    monkeypatch.setattr("services.sandbox_service.settings.MAX_ACTIVE_SANDBOXES", 2)
    create_sandbox_deployment(db, "whoami")
    create_sandbox_deployment(db, "nginx")

    with pytest.raises(SandboxCapacityError) as raised:
        create_sandbox_deployment(db, "whoami")

    assert raised.value.retry_after_seconds >= 30
    assert db.query(Deployment).count() == 2


def test_finished_sandboxes_free_their_slot(db, monkeypatch):
    monkeypatch.setattr("services.sandbox_service.settings.MAX_ACTIVE_SANDBOXES", 1)
    first = create_sandbox_deployment(db, "whoami")
    first.status = "expired"
    db.add(first)
    db.commit()

    create_sandbox_deployment(db, "whoami")


def test_sandbox_endpoint_returns_429_with_retry_after_when_full(db, monkeypatch):
    monkeypatch.setattr("services.sandbox_service.settings.MAX_ACTIVE_SANDBOXES", 1)
    monkeypatch.setattr("api.routes.sandbox.dispatch_sandbox_deployment", MagicMock())
    create_sandbox_demo(template="whoami", db=db)

    with pytest.raises(HTTPException) as raised:
        create_sandbox_demo(template="whoami", db=db)

    assert raised.value.status_code == 429
    assert int(raised.value.headers["Retry-After"]) >= 30


def test_sandbox_that_could_not_be_dispatched_frees_its_slot(db, monkeypatch):
    monkeypatch.setattr("services.sandbox_service.settings.MAX_ACTIVE_SANDBOXES", 1)
    monkeypatch.setattr("services.providers.vm_docker.settings.GITHUB_DISPATCH_TOKEN", "")

    with pytest.raises(HTTPException) as raised:
        create_sandbox_demo(template="whoami", db=db)

    assert raised.value.status_code == 400
    assert db.query(Deployment).one().status == "failed"
    create_sandbox_deployment(db, "whoami")  # the slot is free again


def test_zero_sandbox_cap_disables_the_demo(db, monkeypatch):
    monkeypatch.setattr("services.sandbox_service.settings.MAX_ACTIVE_SANDBOXES", 0)
    with pytest.raises(SandboxCapacityError, match="disabled"):
        create_sandbox_deployment(db, "whoami")


def test_teardown_asks_the_runner_when_dispatch_is_configured(monkeypatch):
    post = MagicMock(return_value=SimpleNamespace(status_code=204))
    run = MagicMock()
    monkeypatch.setattr("services.providers.vm_docker.httpx.post", post)
    monkeypatch.setattr("services.providers.vm_docker.subprocess.run", run)
    monkeypatch.setattr("services.providers.vm_docker.settings.GITHUB_DISPATCH_TOKEN", "token")
    monkeypatch.setattr("services.providers.vm_docker.settings.GITHUB_REPOSITORY", "example/platform")

    VMRunnerProvider().teardown(Deployment(id=42, name="sandbox-whoami-42"))

    payload = post.call_args.kwargs["json"]
    assert payload == {"event_type": "teardown_sandbox", "client_payload": {"deployment_id": "42"}}
    run.assert_not_called()


def test_teardown_raises_when_github_rejects_it(monkeypatch):
    rejected = SimpleNamespace(status_code=403, text="Resource not accessible", headers={})
    monkeypatch.setattr("services.providers.vm_docker.httpx.post", MagicMock(return_value=rejected))
    monkeypatch.setattr("services.providers.vm_docker.settings.GITHUB_DISPATCH_TOKEN", "token")

    with pytest.raises(RuntimeError, match="teardown_sandbox"):
        VMRunnerProvider().teardown(Deployment(id=42, name="sandbox-whoami-42"))


def test_sweeper_keeps_sandbox_active_until_teardown_succeeds(db, monkeypatch):
    now = datetime.now(timezone.utc)
    deployment = Deployment(
        owner_id=0,
        name="sandbox-whoami-1",
        namespace="sandbox",
        image="mpepping/whoami:latest",
        port=20001,
        container_port=8000,
        replicas=1,
        is_sandbox=True,
        status="running",
        expires_at=now - timedelta(minutes=1),
        metadata_json={},
    )
    db.add(deployment)
    db.commit()
    provider = MagicMock()
    provider.teardown.side_effect = RuntimeError("GitHub is down")
    monkeypatch.setattr("services.sandbox_sweeper.get_deployment_provider", MagicMock(return_value=provider))

    assert sweep_expired_sandboxes(db, now=now) == 0
    db.refresh(deployment)
    assert deployment.status == "running"
    assert deployment.metadata_json["teardown_error"] == "GitHub is down"

    provider.teardown.side_effect = None
    assert sweep_expired_sandboxes(db, now=now) == 1
    db.refresh(deployment)
    assert deployment.status == "expired"
