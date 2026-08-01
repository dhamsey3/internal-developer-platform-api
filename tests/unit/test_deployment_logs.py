from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.routes.deployments import get_deployment_logs
from auth.jwt_utils import create_access_token
from database.models import Base, Deployment


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine)()


def _deployment(db, owner_id=0, is_sandbox=True, status="running", metadata=None):
    deployment = Deployment(
        owner_id=owner_id,
        name="sandbox-whoami-101" if is_sandbox else "private-app",
        namespace="sandbox" if is_sandbox else "destination-home-vm",
        image="mpepping/whoami:latest",
        port=20101,
        container_port=8000,
        replicas=1,
        status=status,
        is_sandbox=is_sandbox,
        metadata_json=metadata or {},
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    return deployment


def test_running_sandbox_logs_are_read_from_docker(monkeypatch):
    engine, db = _session()

    def run(command, **kwargs):
        assert command == ["docker", "logs", "--tail", "100", "container-101"]
        return SimpleNamespace(returncode=0, stdout="line 1\nline 2\n", stderr="")

    monkeypatch.setattr("services.providers.vm_docker.subprocess.run", run)
    try:
        deployment = _deployment(db, metadata={"runtime_id": "container-101", "logs": "persisted"})

        result = get_deployment_logs(deployment.id, db, "")

        assert result["deployment_id"] == str(deployment.id)
        assert result["logs"] == ["line 1", "line 2"]
        assert "fetched_at" in result
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_running_sandbox_logs_use_configured_provider(monkeypatch):
    engine, db = _session()
    provider = MagicMock()
    provider.get_logs.return_value = ["provider line"]
    monkeypatch.setattr("api.routes.deployments.get_deployment_provider", MagicMock(return_value=provider))
    try:
        deployment = _deployment(db, metadata={"provider": "vm_docker"})

        result = get_deployment_logs(deployment.id, db, "")

        assert result["logs"] == ["provider line"]
        provider.get_logs.assert_called_once()
        assert provider.get_logs.call_args.args[0].id == deployment.id
        assert provider.get_logs.call_args.kwargs["tail"] == 100
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_expired_sandbox_logs_use_persisted_fallback():
    engine, db = _session()
    try:
        deployment = _deployment(db, status="expired", metadata={"logs": "old line\nlast line"})

        result = get_deployment_logs(deployment.id, db, "")

        assert result["logs"] == ["old line", "last line"]
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_expired_sandbox_without_logs_reports_purged_message():
    engine, db = _session()
    try:
        deployment = _deployment(db, status="expired")

        result = get_deployment_logs(deployment.id, db, "")

        assert result["logs"] == ["Container terminated and logs purged."]
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_regular_deployment_logs_require_owner_token():
    engine, db = _session()
    try:
        deployment = _deployment(db, owner_id=7, is_sandbox=False)

        try:
            get_deployment_logs(deployment.id, db, "")
        except HTTPException as exc:
            assert exc.status_code == 401
        else:
            raise AssertionError("Expected regular deployment logs to require authentication")
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_regular_deployment_logs_allow_owner_token(monkeypatch):
    engine, db = _session()
    monkeypatch.setattr(
        "services.providers.vm_docker.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr=""),
    )
    try:
        deployment = _deployment(
            db,
            owner_id=7,
            is_sandbox=False,
            metadata={"runtime_id": "container-201", "logs": "private log"},
        )
        token = create_access_token({"sub": "7", "role": "user"})

        result = get_deployment_logs(deployment.id, db, f"Bearer {token}")

        assert result["logs"] == ["private log"]
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
