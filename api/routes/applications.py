from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import secrets

from fastapi import Header

from app.config import settings
from api.schemas import ApplicationCreateRequest, ApplicationDeploymentCallback, ApplicationResponse
from auth.rbac import get_current_user
from database.models import Application, Destination, User
from database.session import get_db
from services.application_service import create_application, dispatch_application_deployment
from services.destination_service import destination_readiness

router = APIRouter()


def _response(application: Application, destination: Destination) -> dict:
    return {
        "id": application.id,
        "owner_id": application.owner_id,
        "destination_id": application.destination_id,
        "name": application.name,
        "description": application.description,
        "source_type": application.source_type,
        "repository_url": application.repository_url,
        "image": application.image,
        "port": application.port,
        "environment": application.environment,
        "status": application.status,
        "resource_requests": application.resource_requests or [],
        "metadata_json": application.metadata_json or {},
        "created_at": application.created_at,
        "destination": {
            "id": destination.id,
            "name": destination.name,
            "kind": destination.kind,
            "provider": destination.provider,
            "environment": destination.environment,
            "status": destination.status,
            "config": destination.config or {},
            "capabilities": destination.capabilities or [],
            "is_default": destination.is_default,
            "readiness": destination_readiness(destination),
        },
    }


@router.get("", response_model=list[ApplicationResponse])
def list_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    applications = (
        db.query(Application)
        .filter(Application.owner_id == current_user.id)
        .order_by(Application.created_at.desc())
        .all()
    )
    destinations = {
        destination.id: destination
        for destination in db.query(Destination)
        .filter(Destination.id.in_([application.destination_id for application in applications]))
        .all()
    } if applications else {}
    return [_response(application, destinations[application.destination_id]) for application in applications]


@router.post("", response_model=ApplicationResponse, status_code=201)
def create_application_route(
    request: ApplicationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        application = create_application(db, current_user, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    destination = db.query(Destination).filter(Destination.id == application.destination_id).one()
    return _response(application, destination)


@router.post("/{application_id}/deploy", response_model=ApplicationResponse, status_code=202)
def deploy_application_route(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    application = (
        db.query(Application)
        .filter(Application.id == application_id, Application.owner_id == current_user.id)
        .first()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.source_type != "container_image":
        raise HTTPException(status_code=409, detail="Repository builds are not configured yet")
    destination = db.query(Destination).filter(Destination.id == application.destination_id).one()
    try:
        dispatch_application_deployment(application, destination)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.add(application)
    db.commit()
    db.refresh(application)
    return _response(application, destination)


@router.post("/{application_id}/deployment-callback", response_model=ApplicationResponse)
def application_deployment_callback(
    application_id: int,
    callback: ApplicationDeploymentCallback,
    x_deployment_token: str = Header(default=""),
    db: Session = Depends(get_db),
):
    if not settings.DEPLOYMENT_CALLBACK_TOKEN or not secrets.compare_digest(
        x_deployment_token,
        settings.DEPLOYMENT_CALLBACK_TOKEN,
    ):
        raise HTTPException(status_code=401, detail="Invalid deployment callback token")
    application = db.query(Application).filter(Application.id == application_id).first()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    destination = db.query(Destination).filter(Destination.id == application.destination_id).one()
    metadata = application.metadata_json or {}
    application.status = callback.status
    application.metadata_json = {
        **metadata,
        "url": callback.url,
        "last_error": callback.error,
    }
    db.add(application)
    db.commit()
    db.refresh(application)
    return _response(application, destination)
