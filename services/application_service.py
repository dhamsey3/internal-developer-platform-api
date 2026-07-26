from sqlalchemy.orm import Session

from api.schemas import ApplicationCreateRequest
from database.models import Application, Destination, User
from services.deployment_service import validate_docker_image
from services.destination_service import destination_readiness


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
        status="ready_to_deploy" if readiness["ready"] and not requested_resources else "setup_required",
        resource_requests=requested_resources,
        metadata_json={
            "destination_readiness": readiness,
            "resource_readiness": {
                resource: {
                    "ready": False,
                    "message": "Resource provisioning is not configured yet",
                }
                for resource in requested_resources
            },
        },
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application
