from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas import DeploymentCreateRequest, DeploymentResponse
from auth.rbac import get_current_user
from database.models import Deployment, User
from database.session import get_db
from services.deployment_service import (
    delete_kubernetes_deployment,
    get_kubernetes_deployment_status,
    provision_application,
)

router = APIRouter()

@router.post("", response_model=DeploymentResponse, status_code=201)
def create_deployment_route(
    request: DeploymentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return provision_application(db, current_user, request)

@router.get("/{id}", response_model=DeploymentResponse)
def get_deployment(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deployment = db.query(Deployment).filter(Deployment.id == id, Deployment.owner_id == current_user.id).first()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
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
