from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from api.schemas import ApplicationCreateRequest
from database.models import Application, Destination, User
from services.deployment_service import validate_docker_image
from services.destination_service import destination_readiness, resources_readiness


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


def dispatch_application_deployment(application: Application, destination: Destination) -> None:
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
        "deployment_requested_at": datetime.now(UTC).isoformat(),
    }
