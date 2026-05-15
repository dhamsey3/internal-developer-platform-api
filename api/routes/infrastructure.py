from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas import InfrastructureCreateRequest, InfrastructureResponse
from auth.rbac import get_current_user
from database.models import Infrastructure, User
from database.session import get_db
from services.infra_queue import InfrastructureQueueError, enqueue_infrastructure_job
from services.infra_service import validate_infrastructure_config

router = APIRouter()


@router.post("/create", response_model=InfrastructureResponse, status_code=202)
def create_infrastructure(
    request: InfrastructureCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validation_error = validate_infrastructure_config(request.name, request.cloud_provider, request.config)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)

    infra = Infrastructure(
        owner_id=current_user.id,
        name=request.name,
        cloud_provider=request.cloud_provider,
        config=request.config,
        status="queued",
    )
    db.add(infra)
    db.commit()
    db.refresh(infra)
    try:
        enqueue_infrastructure_job("provision", infra.id, background_tasks)
    except InfrastructureQueueError as exc:
        infra.status = "failed"
        infra.last_error = str(exc)
        db.add(infra)
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc))
    return infra


@router.delete("/{id}")
def delete_infrastructure(
    id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    infra = db.query(Infrastructure).filter(Infrastructure.id == id, Infrastructure.owner_id == current_user.id).first()
    if not infra:
        raise HTTPException(status_code=404, detail="Infrastructure not found")
    if infra.status in {"deleting", "deleted"}:
        return {"id": id, "status": infra.status}
    if infra.status in {"queued", "provisioning"}:
        raise HTTPException(status_code=409, detail="Infrastructure is still provisioning")

    infra.status = "delete_queued"
    infra.last_error = None
    db.add(infra)
    db.commit()
    try:
        enqueue_infrastructure_job("destroy", infra.id, background_tasks)
    except InfrastructureQueueError as exc:
        infra.status = "delete_failed"
        infra.last_error = str(exc)
        db.add(infra)
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc))
    return {"id": id, "status": infra.status}


@router.get("/{id}", response_model=InfrastructureResponse)
def get_infrastructure(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    infra = db.query(Infrastructure).filter(Infrastructure.id == id, Infrastructure.owner_id == current_user.id).first()
    if not infra:
        raise HTTPException(status_code=404, detail="Infrastructure not found")
    return infra
