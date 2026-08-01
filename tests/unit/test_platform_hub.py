from types import SimpleNamespace
from unittest.mock import MagicMock
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.schemas import ApplicationCreateRequest
from api.schemas import ApplicationDeploymentCallback
from api.routes.applications import application_deployment_callback
from database.models import Application, Base, Deployment, Destination, User
from services.application_service import create_application
from services.application_service import dispatch_application_deployment
from services.application_service import mark_stale_application_deployments
from services.destination_service import destination_readiness, resources_readiness


def test_linux_destination_reports_missing_deployment_workflow():
    destination = Destination(
        name="home-vm",
        kind="linux_docker",
        provider="existing_server",
        environment="development",
        config={"enabled": True, "runner_label": "idp-vm", "github_repository": "example/platform", "deployment_workflow": False},
        capabilities=["containers"],
    )

    readiness = destination_readiness(destination)

    assert readiness["ready"] is False
    assert readiness["checks"]["runner_label"] is True
    assert "Configure an application deployment workflow" in readiness["missing"]


def test_application_catalog_records_destination_and_resource_gaps():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = test_session()
    try:
        user = User(username="platform-user", hashed_password="not-used")
        destination = Destination(
            name="home-vm",
            kind="linux_docker",
            provider="existing_server",
            environment="development",
            config={"enabled": True, "runner_label": "idp-vm", "github_repository": "example/platform", "deployment_workflow": False},
            capabilities=["containers"],
        )
        db.add_all([user, destination])
        db.commit()
        db.refresh(user)
        db.refresh(destination)

        request = ApplicationCreateRequest(
            name="orders-api",
            source_type="container_image",
            image="ghcr.io/example/orders-api:1.0.0",
            port=8080,
            destination_id=destination.id,
            resource_requests=["postgresql", "secrets"],
        )
        application = create_application(db, user, request)

        assert application.status == "setup_required"
        assert application.destination_id == destination.id
        assert application.resource_requests == ["postgresql", "secrets"]
        assert application.metadata_json["destination_readiness"]["ready"] is False
        assert application.metadata_json["resource_readiness"]["postgresql"]["ready"] is True
        assert db.query(Application).filter(Application.name == "orders-api").one()
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_linux_destination_supports_postgresql_and_secrets():
    destination = Destination(name="home-vm", kind="linux_docker", provider="existing_server")

    readiness = resources_readiness(destination, ["postgresql", "secrets", "redis"])

    assert readiness["postgresql"]["ready"] is True
    assert readiness["secrets"]["ready"] is True
    assert readiness["redis"]["ready"] is False


def test_dispatch_queues_sanitized_application_payload(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = test_session()
    monkeypatch.setattr("services.application_service.settings.GITHUB_DISPATCH_TOKEN", "test-token")
    monkeypatch.setattr(
        "services.application_service.settings.GITHUB_REPOSITORY",
        "example/platform",
    )
    response = SimpleNamespace(status_code=204)
    post = MagicMock(return_value=response)
    monkeypatch.setattr("services.application_service.httpx.post", post)
    try:
        destination = Destination(
            name="home-vm",
            kind="linux_docker",
            provider="existing_server",
            config={
                "enabled": True,
                "runner_label": "idp-vm",
                "github_repository": "example/platform",
                "deployment_workflow": True,
            },
        )
        db.add(destination)
        db.commit()
        db.refresh(destination)
        application = Application(
            owner_id=1,
            destination_id=destination.id,
            name="orders-api",
            source_type="container_image",
            image="ghcr.io/example/orders-api:1.0.0",
            port=8080,
            status="ready_to_deploy",
            resource_requests=["postgresql"],
            metadata_json={"resource_readiness": {"postgresql": {"ready": True}}},
        )
        db.add(application)
        db.commit()
        db.refresh(application)

        dispatch_application_deployment(db, application, destination)

        request = post.call_args.kwargs
        assert request["json"]["ref"] == "main"
        assert request["json"]["inputs"]["host_port"] == str(10000 + application.id)
        assert len(request["json"]["inputs"]["attempt_id"]) == 32
        assert "token" not in request["json"]["inputs"]
        assert application.status == "queued"
        assert application.metadata_json["deployment_attempt_id"] == request["json"]["inputs"]["attempt_id"]
        deployment = next(
            item
            for item in db.query(Deployment).all()
            if item.metadata_json["application_id"] == application.id
        )
        assert deployment.status == "queued"
        assert deployment.namespace == "destination-home-vm"
        assert deployment.metadata_json["deployment_attempt_id"] == request["json"]["inputs"]["attempt_id"]
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_authenticated_callback_updates_application_status(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = test_session()
    monkeypatch.setattr("api.routes.applications.settings.DEPLOYMENT_CALLBACK_TOKEN", "callback-token")
    try:
        destination = Destination(
            name="home-vm",
            kind="linux_docker",
            provider="existing_server",
            config={
                "enabled": True,
                "runner_label": "idp-vm",
                "github_repository": "example/platform",
                "deployment_workflow": True,
            },
        )
        application = Application(
            owner_id=1,
            destination_id=1,
            name="orders-api",
            source_type="container_image",
            image="nginx:1.25-alpine",
            status="deploying",
            metadata_json={"deployment_attempt_id": "a" * 32},
        )
        db.add_all([destination, application])
        db.commit()
        db.refresh(application)

        response = application_deployment_callback(
            application.id,
            ApplicationDeploymentCallback(
                status="running",
                attempt_id="a" * 32,
                url="http://172.19.30.97:10001",
                health_url="http://172.19.30.97:10001/health",
                runtime_id="container-123",
                logs="started",
            ),
            "callback-token",
            db,
        )

        assert response["status"] == "running"
        assert response["metadata_json"]["url"] == "http://172.19.30.97:10001"
        assert response["metadata_json"]["health_url"] == "http://172.19.30.97:10001/health"
        deployment = next(
            item
            for item in db.query(Deployment).all()
            if item.metadata_json["application_id"] == application.id
        )
        assert deployment.status == "running"
        assert deployment.url == "http://172.19.30.97:10001"
        assert deployment.metadata_json["runtime_id"] == "container-123"
        assert deployment.metadata_json["health_url"] == "http://172.19.30.97:10001/health"
        assert deployment.metadata_json["logs"] == "started"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_failed_callback_updates_only_matching_runtime_deployment(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = test_session()
    monkeypatch.setattr("api.routes.applications.settings.DEPLOYMENT_CALLBACK_TOKEN", "callback-token")
    try:
        destination = Destination(
            name="home-vm",
            kind="linux_docker",
            provider="existing_server",
            config={
                "enabled": True,
                "runner_label": "idp-vm",
                "github_repository": "example/platform",
                "deployment_workflow": True,
            },
        )
        application = Application(
            owner_id=1,
            destination_id=1,
            name="orders-api",
            source_type="container_image",
            image="nginx:1.25-alpine",
            status="deploying",
            metadata_json={"host_port": 10001, "deployment_attempt_id": "b" * 32},
        )
        unrelated = Deployment(
            owner_id=1,
            name="orders-api",
            namespace="destination-home-vm",
            image="nginx:1.25-alpine",
            port=80,
            status="running",
            metadata_json={"application_id": 999},
        )
        db.add_all([destination, application, unrelated])
        db.commit()
        db.refresh(application)
        db.refresh(unrelated)

        application_deployment_callback(
            application.id,
            ApplicationDeploymentCallback(
                status="failed",
                attempt_id="b" * 32,
                error="container failed health check",
                logs="listen tcp: bind failed",
            ),
            "callback-token",
            db,
        )

        failed = next(
            item
            for item in db.query(Deployment).all()
            if item.metadata_json["application_id"] == application.id
        )
        db.refresh(unrelated)
        assert failed.status == "failed"
        assert failed.last_error == "container failed health check"
        assert failed.metadata_json["logs"] == "listen tcp: bind failed"
        assert unrelated.status == "running"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_callback_rejects_missing_and_incorrect_tokens(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = test_session()
    monkeypatch.setattr("api.routes.applications.settings.DEPLOYMENT_CALLBACK_TOKEN", "callback-token")
    try:
        destination = Destination(name="home-vm", kind="linux_docker", provider="existing_server")
        application = Application(
            owner_id=1,
            destination_id=1,
            name="orders-api",
            source_type="container_image",
            image="nginx:1.25-alpine",
            status="deploying",
            metadata_json={"deployment_attempt_id": "c" * 32},
        )
        db.add_all([destination, application])
        db.commit()
        db.refresh(application)

        for token in ("", "wrong-token"):
            try:
                application_deployment_callback(
                    application.id,
                    ApplicationDeploymentCallback(status="running", attempt_id="c" * 32),
                    token,
                    db,
                )
            except Exception as exc:
                assert getattr(exc, "status_code") == 401
            else:
                raise AssertionError("Expected callback token to be rejected")
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_stale_callback_cannot_overwrite_newer_attempt(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = test_session()
    monkeypatch.setattr("api.routes.applications.settings.DEPLOYMENT_CALLBACK_TOKEN", "callback-token")
    try:
        destination = Destination(name="home-vm", kind="linux_docker", provider="existing_server")
        application = Application(
            owner_id=1,
            destination_id=1,
            name="orders-api",
            source_type="container_image",
            image="nginx:1.25-alpine",
            status="deploying",
            metadata_json={"deployment_attempt_id": "d" * 32},
        )
        db.add_all([destination, application])
        db.commit()
        db.refresh(application)

        try:
            application_deployment_callback(
                application.id,
                ApplicationDeploymentCallback(status="running", attempt_id="e" * 32, runtime_id="old"),
                "callback-token",
                db,
            )
        except Exception as exc:
            assert getattr(exc, "status_code") == 409
        else:
            raise AssertionError("Expected stale callback to be rejected")
        db.refresh(application)
        assert application.status == "deploying"
        assert application.metadata_json.get("runtime_id") is None
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_duplicate_success_callback_is_idempotent(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = test_session()
    monkeypatch.setattr("api.routes.applications.settings.DEPLOYMENT_CALLBACK_TOKEN", "callback-token")
    try:
        destination = Destination(name="home-vm", kind="linux_docker", provider="existing_server")
        application = Application(
            owner_id=1,
            destination_id=1,
            name="orders-api",
            source_type="container_image",
            image="nginx:1.25-alpine",
            status="deploying",
            metadata_json={"deployment_attempt_id": "f" * 32},
        )
        db.add_all([destination, application])
        db.commit()
        db.refresh(application)
        callback = ApplicationDeploymentCallback(
            status="running",
            attempt_id="f" * 32,
            url="http://example.test:10001",
            runtime_id="container-1",
            logs="ready",
        )

        application_deployment_callback(application.id, callback, "callback-token", db)
        application_deployment_callback(application.id, callback, "callback-token", db)

        deployments = db.query(Deployment).all()
        assert len(deployments) == 1
        assert deployments[0].status == "running"
        assert deployments[0].metadata_json["runtime_id"] == "container-1"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_stale_application_deployment_is_marked_failed():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = test_session()
    try:
        destination = Destination(name="home-vm", kind="linux_docker", provider="existing_server")
        application = Application(
            owner_id=1,
            destination_id=1,
            name="orders-api",
            source_type="container_image",
            image="nginx:1.25-alpine",
            status="queued",
            metadata_json={
                "deployment_attempt_id": "1" * 32,
                "deployment_requested_at": (datetime.now(UTC) - timedelta(minutes=45)).isoformat(),
            },
        )
        db.add_all([destination, application])
        db.commit()
        db.refresh(application)

        changed = mark_stale_application_deployments(db, [application])
        db.commit()

        assert changed is True
        assert application.status == "failed"
        assert "timeout" in application.metadata_json["last_error"]
        deployment = db.query(Deployment).one()
        assert deployment.status == "failed"
        assert "timeout" in deployment.last_error
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_application_rejects_unknown_destination():
    request = ApplicationCreateRequest(
        name="orders-api",
        source_type="container_image",
        image="nginx:1.25-alpine",
        destination_id=99,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    try:
        create_application(db, SimpleNamespace(id=1), request)
    except ValueError as exc:
        assert str(exc) == "Destination not found"
    else:
        raise AssertionError("Expected an unknown destination to be rejected")
