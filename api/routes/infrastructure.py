from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas import InfrastructureCreateRequest, InfrastructureResponse
from auth.rbac import get_current_user
from database.models import Infrastructure, User
from database.session import get_db
from services.infra_service import provision_infrastructure, destroy_infrastructure

router = APIRouter()

@router.post("/create", response_model=InfrastructureResponse, status_code=201)
def create_infrastructure(
    request: InfrastructureCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    infra = Infrastructure(
        owner_id=current_user.id,
        name=request.name,
        cloud_provider=request.cloud_provider,
        config=request.config,
        status="provisioning",
    )
    db.add(infra)
    db.commit()
    db.refresh(infra)
    result = provision_infrastructure(request.name, request.cloud_provider, request.config)
    if result is True:
        infra.status = "ready"
    else:
        infra.status = "failed"
        infra.last_error = str(result)
    db.add(infra)
    db.commit()
    db.refresh(infra)
    return infra

@router.delete("/{id}")
def delete_infrastructure(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    infra = db.query(Infrastructure).filter(Infrastructure.id == id, Infrastructure.owner_id == current_user.id).first()
    if not infra:
        raise HTTPException(status_code=404, detail="Infrastructure not found")
    result = destroy_infrastructure(infra.name, infra.cloud_provider, infra.config or {})
    if result is True:
        infra.status = "deleted"
        db.add(infra)
        db.commit()
        return {"id": id, "status": "deleted"}
    infra.status = "delete_failed"
    infra.last_error = str(result)
    db.add(infra)
    db.commit()
    raise HTTPException(status_code=500, detail=str(result))

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
