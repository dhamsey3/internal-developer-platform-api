import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from api.schemas import DeploymentCreateRequest, DeploymentResponse, DeploymentStatusPatch
from auth.rbac import get_current_user
from database.models import Deployment, User
from database.session import get_db
from services.deployment_service import (
    delete_kubernetes_deployment,
    get_kubernetes_deployment_status,
    provision_application,
)
from services.application_service import mark_stale_runtime_deployments

router = APIRouter()


def _user_id_from_authorization(authorization: str) -> Optional[int]:
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
    subject = payload.get("sub")
    try:
        return int(subject)
    except (TypeError, ValueError):
        return None


@router.get("", response_model=list[DeploymentResponse])
def list_deployments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deployments = (
        db.query(Deployment)
        .filter(Deployment.owner_id == current_user.id)
        .order_by(Deployment.created_at.desc())
        .all()
    )
    if mark_stale_runtime_deployments(db, deployments):
        db.commit()
        deployments = (
            db.query(Deployment)
            .filter(Deployment.owner_id == current_user.id)
            .order_by(Deployment.created_at.desc())
            .all()
        )
    return deployments


@router.post("", response_model=DeploymentResponse, status_code=201)
def create_deployment_route(
    request: DeploymentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return provision_application(db, current_user, request)


@router.patch("/{id}", response_model=DeploymentResponse)
def patch_deployment_status(
    id: int,
    request: DeploymentStatusPatch,
    x_deployment_token: str = Header(default=""),
    db: Session = Depends(get_db),
):
    if not settings.DEPLOYMENT_CALLBACK_TOKEN or not secrets.compare_digest(
        x_deployment_token,
        settings.DEPLOYMENT_CALLBACK_TOKEN,
    ):
        raise HTTPException(status_code=401, detail="Invalid deployment callback token")
    deployment = db.query(Deployment).filter(Deployment.id == id, Deployment.is_sandbox.is_(True)).first()
    if deployment is None:
        raise HTTPException(status_code=404, detail="Sandbox deployment not found")

    metadata = deployment.metadata_json or {}
    deployment.status = request.status
    deployment.url = request.url or deployment.url
    deployment.last_error = request.error
    if request.host_port:
        deployment.port = request.host_port
    deployment.metadata_json = {
        **metadata,
        "runtime_id": request.runtime_id or metadata.get("runtime_id"),
        "logs": request.logs or metadata.get("logs"),
        "host_port": request.host_port or metadata.get("host_port"),
    }
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    return deployment

@router.get("/{id}", response_model=DeploymentResponse)
def get_deployment(
    id: int,
    db: Session = Depends(get_db),
    authorization: str = Header(default=""),
):
    deployment = db.query(Deployment).filter(Deployment.id == id).first()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    if not deployment.is_sandbox and deployment.owner_id != _user_id_from_authorization(authorization):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if mark_stale_runtime_deployments(db, [deployment]):
        db.commit()
        db.refresh(deployment)
    if deployment.status == "running":
        try:
            deployment.metadata_json = {
                **(deployment.metadata_json or {}),
                "kubernetes_status": get_kubernetes_deployment_status(deployment.namespace, deployment.name),
            }
            db.add(deployment)
            db.commit()
            db.refresh(deployment)
        except Exception as exc:
            deployment.metadata_json = {**(deployment.metadata_json or {}), "status_error": str(exc)}
    return deployment

@router.delete("/{id}")
def delete_deployment(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deployment = db.query(Deployment).filter(Deployment.id == id, Deployment.owner_id == current_user.id).first()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    delete_kubernetes_deployment(deployment.namespace, deployment.name)
    deployment.status = "deleted"
    db.add(deployment)
    db.commit()
    return {"id": id, "status": "deleted"}
