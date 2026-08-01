from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from api.schemas import ApplicationCreateRequest
from database.models import Application, Deployment, Destination, User
from services.deployment_service import validate_docker_image
from services.destination_service import destination_readiness, resources_readiness

ACTIVE_DEPLOYMENT_STATUSES = {"queued", "deploying"}
DEPLOYMENT_CALLBACK_TIMEOUT = timedelta(minutes=30)


def create_application(
    db: Session,
    user: User,
    request: ApplicationCreateRequest,
) -> Application:
    destination = db.query(Destination).filter(Destination.id == request.destination_id).first()
    if destination is None:
        raise ValueError("Destination not found")

    existing = (
        db.query(Application)
        .filter(Application.owner_id == user.id, Application.name == request.name)
        .first()
    )
    if existing:
        raise ValueError("An application with this name already exists")

    if request.image:
        validate_docker_image(request.image)

    readiness = destination_readiness(destination)
    requested_resources = request.resource_requests
    resource_status = resources_readiness(destination, requested_resources)
    resources_ready = all(item["ready"] for item in resource_status.values())
    application = Application(
        owner_id=user.id,
        destination_id=destination.id,
        name=request.name,
        description=request.description,
        source_type=request.source_type,
        repository_url=request.repository_url,
        image=request.image,
        port=request.port,
        environment=request.environment,
        status="ready_to_deploy" if readiness["ready"] and resources_ready else "setup_required",
        resource_requests=requested_resources,
        metadata_json={
            "destination_readiness": readiness,
            "resource_readiness": resource_status,
        },
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


def _application_runtime_namespace(destination: Destination) -> str:
    return f"destination-{destination.name}"[:63].rstrip("-")


def _application_runtime_metadata(application: Application, destination: Destination, host_port: int) -> dict:
    return {
        "application_id": application.id,
        "destination_id": destination.id,
        "destination_name": destination.name,
        "destination_kind": destination.kind,
        "runtime": "linux_docker",
        "host_port": host_port,
        "deployment_attempt_id": (application.metadata_json or {}).get("deployment_attempt_id"),
        "deployment_requested_at": (application.metadata_json or {}).get("deployment_requested_at"),
    }


def upsert_application_runtime_deployment(
    db: Session,
    application: Application,
    destination: Destination,
    status: str,
    url: Optional[str] = None,
    error: Optional[str] = None,
    runtime_id: Optional[str] = None,
    health_url: Optional[str] = None,
    logs: Optional[str] = None,
) -> Deployment:
    metadata = application.metadata_json or {}
    host_port = metadata.get("host_port") or 10000 + application.id
    deployment_candidates = (
        db.query(Deployment)
        .filter(
            Deployment.owner_id == application.owner_id,
            Deployment.name == application.name,
        )
        .order_by(Deployment.created_at.desc())
        .all()
    )
    deployment = next(
        (
            item
            for item in deployment_candidates
            if (item.metadata_json or {}).get("application_id") == application.id
        ),
        None,
    )
    if deployment is None:
        deployment = Deployment(
            owner_id=application.owner_id,
            name=application.name,
            namespace=_application_runtime_namespace(destination),
            image=application.image or "repository-build-pending",
            port=application.port,
            replicas=1,
            ingress_host=None,
        )
        db.add(deployment)

    deployment.image = application.image or deployment.image
    deployment.port = application.port
    deployment.url = url or metadata.get("url") or deployment.url
    deployment.status = status
    deployment.last_error = error
    deployment.metadata_json = {
        **(deployment.metadata_json or {}),
        **_application_runtime_metadata(application, destination, host_port),
        "runtime_id": runtime_id or (deployment.metadata_json or {}).get("runtime_id"),
        "health_url": health_url or (deployment.metadata_json or {}).get("health_url"),
        "logs": logs or (deployment.metadata_json or {}).get("logs"),
    }
    return deployment


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def mark_stale_application_deployments(
    db: Session,
    applications: list[Application],
    now: Optional[datetime] = None,
) -> bool:
    now = now or datetime.now(UTC)
    changed = False
    for application in applications:
        if application.status not in ACTIVE_DEPLOYMENT_STATUSES:
            continue
        metadata = application.metadata_json or {}
        requested_at = _parse_timestamp(metadata.get("deployment_requested_at"))
        if requested_at is None or now - requested_at <= DEPLOYMENT_CALLBACK_TIMEOUT:
            continue
        error = "Deployment callback was not received before the timeout"
        application.status = "failed"
        application.metadata_json = {
            **metadata,
            "last_error": error,
            "timed_out_at": now.isoformat(),
        }
        destination = db.query(Destination).filter(Destination.id == application.destination_id).first()
        if destination is not None:
            upsert_application_runtime_deployment(
                db,
                application,
                destination,
                "failed",
                error=error,
            )
        db.add(application)
        changed = True
    return changed


def mark_stale_runtime_deployments(
    db: Session,
    deployments: list[Deployment],
    now: Optional[datetime] = None,
) -> bool:
    now = now or datetime.now(UTC)
    changed = False
    for deployment in deployments:
        if deployment.status not in ACTIVE_DEPLOYMENT_STATUSES:
            continue
        metadata = deployment.metadata_json or {}
        requested_at = _parse_timestamp(metadata.get("deployment_requested_at"))
        if requested_at is None or now - requested_at <= DEPLOYMENT_CALLBACK_TIMEOUT:
            continue
        deployment.status = "failed"
        deployment.last_error = "Deployment callback was not received before the timeout"
        deployment.metadata_json = {
            **metadata,
            "timed_out_at": now.isoformat(),
        }
        db.add(deployment)
        changed = True
    return changed


def dispatch_application_deployment(db: Session, application: Application, destination: Destination) -> None:
    if not settings.GITHUB_DISPATCH_TOKEN:
        raise ValueError("GitHub application deployment dispatch is not configured")
    readiness = destination_readiness(destination)
    if not readiness["ready"]:
        raise ValueError("Destination is not ready for application deployments")

    metadata = application.metadata_json or {}
    resource_status = metadata.get("resource_readiness", {})
    unavailable = [name for name, status in resource_status.items() if not status.get("ready")]
    if unavailable:
        raise ValueError(f"Resources are not ready: {', '.join(unavailable)}")

    host_port = 10000 + application.id
    if host_port > 65535:
        raise ValueError("No host port is available for this application")
    attempt_id = uuid4().hex
    requested_at = datetime.now(UTC).isoformat()
    response = httpx.post(
        (
            f"https://api.github.com/repos/{settings.GITHUB_REPOSITORY}"
            "/actions/workflows/deploy-application.yaml/dispatches"
        ),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {settings.GITHUB_DISPATCH_TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={
            "ref": "main",
            "inputs": {
                "application_id": str(application.id),
                "name": application.name,
                "image": application.image,
                "port": str(application.port),
                "host_port": str(host_port),
                "attempt_id": attempt_id,
                "resources": ",".join(application.resource_requests or []),
            },
        },
        timeout=20,
    )
    if response.status_code != 204:
        raise RuntimeError(f"GitHub rejected the deployment request with status {response.status_code}")
    application.status = "queued"
    application.metadata_json = {
        **metadata,
        "host_port": host_port,
        "deployment_attempt_id": attempt_id,
        "deployment_requested_at": requested_at,
    }
    upsert_application_runtime_deployment(db, application, destination, "queued")
