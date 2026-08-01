from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.schemas import SandboxDemoRequest, SandboxDemoResponse
from database.session import get_db
from services.sandbox_service import SANDBOX_TTL_SECONDS
from services.sandbox_service import create_sandbox_deployment, dispatch_sandbox_deployment

router = APIRouter()


def _response(deployment, template: str) -> dict:
    return {
        "id": deployment.id,
        "owner_id": deployment.owner_id,
        "name": deployment.name,
        "namespace": deployment.namespace,
        "image": deployment.image,
        "port": deployment.port,
        "container_port": deployment.container_port,
        "replicas": deployment.replicas,
        "ingress_host": deployment.ingress_host,
        "url": deployment.url,
        "status": deployment.status,
        "expires_at": deployment.expires_at,
        "is_sandbox": deployment.is_sandbox,
        "metadata_json": deployment.metadata_json or {},
        "last_error": deployment.last_error,
        "created_at": deployment.created_at,
        "template": template,
        "ttl_seconds": SANDBOX_TTL_SECONDS,
    }


@router.post("/demo", response_model=SandboxDemoResponse, status_code=202)
def create_sandbox_demo(
    request: Optional[SandboxDemoRequest] = Body(default=None),
    template: Optional[str] = Query(default=None, regex=r"^[a-z0-9-]+$"),
    db: Session = Depends(get_db),
):
    template_name = template or (request.template if request else None)
    if template_name is None:
        raise HTTPException(status_code=422, detail="template is required")
    try:
        deployment = create_sandbox_deployment(db, template_name)
        dispatch_sandbox_deployment(deployment)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        if "deployment" in locals():
            deployment.status = "failed"
            deployment.last_error = str(exc)
            db.add(deployment)
            db.commit()
        raise HTTPException(status_code=424, detail=str(exc)) from exc

    return _response(deployment, template_name)
