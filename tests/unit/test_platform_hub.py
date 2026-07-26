from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.schemas import ApplicationCreateRequest
from database.models import Application, Base, Destination, User
from services.application_service import create_application
from services.destination_service import destination_readiness


def test_linux_destination_reports_missing_deployment_workflow():
    destination = Destination(
        name="home-vm",
        kind="linux_docker",
        provider="existing_server",
        environment="development",
        config={"enabled": True, "runner_label": "idp-vm", "deployment_workflow": False},
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
            config={"enabled": True, "runner_label": "idp-vm", "deployment_workflow": False},
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
        assert application.metadata_json["resource_readiness"]["postgresql"]["ready"] is False
        assert db.query(Application).filter(Application.name == "orders-api").one()
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
