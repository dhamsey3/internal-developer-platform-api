import secrets
import subprocess
from datetime import datetime, timezone
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

TERMINAL_SANDBOX_STATUSES = {"expired", "failed", "stopped"}
SANDBOX_TRANSITIONS = {
    "queued": {"queued", "running", "failed", "expired", "stopped"},
    "running": {"running", "expired", "failed", "stopped"},
    "deploying": {"deploying", "running", "failed", "expired", "stopped"},
}


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


def _deployment_log_lines(deployment: Deployment) -> list[str]:
    metadata = deployment.metadata_json or {}
    persisted_logs = metadata.get("logs") or ""
    if deployment.status in TERMINAL_SANDBOX_STATUSES:
        return persisted_logs.splitlines() or ["Container terminated and logs purged."]

    container_id = metadata.get("runtime_id") or str(deployment.id)
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", "100", container_id],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return persisted_logs.splitlines() or ["Container terminated and logs purged."]

    output = "\n".join(part for part in [result.stdout, result.stderr] if part)
    if result.returncode == 0 and output:
        return output.splitlines()[-100:]
    return persisted_logs.splitlines() or ["Container terminated and logs purged."]


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

    if deployment.status in TERMINAL_SANDBOX_STATUSES:
        if request.status == deployment.status:
            return deployment
        raise HTTPException(status_code=409, detail="Terminal sandbox deployment state cannot be overwritten")
    allowed = SANDBOX_TRANSITIONS.get(deployment.status, {deployment.status, "failed"})
    if request.status not in allowed:
        raise HTTPException(status_code=409, detail="Illegal sandbox deployment state transition")
    if request.status == deployment.status:
        return deployment

    metadata = deployment.metadata_json or {}
    deployment.status = request.status
    deployment.url = request.url or deployment.url
    deployment.last_error = request.error
    if request.host_port:
        deployment.port = request.host_port
    if request.container_port:
        deployment.container_port = request.container_port
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


@router.get("/{id}/logs")
def get_deployment_logs(
    id: int,
    db: Session = Depends(get_db),
    authorization: str = Header(default=""),
):
    deployment = db.query(Deployment).filter(Deployment.id == id).first()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    if not deployment.is_sandbox and deployment.owner_id != _user_id_from_authorization(authorization):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {
        "deployment_id": str(deployment.id),
        "logs": _deployment_log_lines(deployment),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


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
