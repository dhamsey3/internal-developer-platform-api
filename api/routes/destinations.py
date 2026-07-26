from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.schemas import DestinationResponse
from auth.rbac import get_current_user
from database.models import Destination
from database.session import get_db
from services.destination_service import refresh_destination_status

router = APIRouter()


def _response(destination: Destination) -> dict:
    readiness = refresh_destination_status(destination)
    return {
        "id": destination.id,
        "name": destination.name,
        "kind": destination.kind,
        "provider": destination.provider,
        "environment": destination.environment,
        "status": destination.status,
        "config": destination.config or {},
        "capabilities": destination.capabilities or [],
        "is_default": destination.is_default,
        "readiness": readiness,
    }


@router.get("", response_model=list[DestinationResponse])
def list_destinations(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    destinations = db.query(Destination).order_by(Destination.is_default.desc(), Destination.name).all()
    responses = [_response(destination) for destination in destinations]
    db.commit()
    return responses


@router.get("/{destination_id}", response_model=DestinationResponse)
def get_destination(
    destination_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    destination = db.query(Destination).filter(Destination.id == destination_id).first()
    if destination is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Destination not found")
    response = _response(destination)
    db.commit()
    return response
