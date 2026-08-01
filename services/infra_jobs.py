import logging
from typing import Callable

from database.models import Infrastructure
from database.session import SessionLocal
from services.infra_service import destroy_infrastructure, provision_infrastructure

logger = logging.getLogger(__name__)


TerraformAction = Callable[[str, str, dict], bool | str]


def _run_infrastructure_job(
    infrastructure_id: int,
    action: TerraformAction,
    in_progress_status: str,
    success_status: str,
    failure_status: str,
) -> None:
    db = SessionLocal()
    infra = None
    try:
        infra = db.get(Infrastructure, infrastructure_id)
        if infra is None:
            logger.warning("Infrastructure job skipped; id %s no longer exists", infrastructure_id)
            return

        infra.status = in_progress_status
        infra.last_error = None
        db.add(infra)
        db.commit()
        db.refresh(infra)

        result = action(infra.name, infra.cloud_provider, infra.config or {})
        infra.status = success_status if result is True else failure_status
        infra.last_error = None if result is True else str(result)
        db.add(infra)
        db.commit()
    except Exception as exc:
        logger.exception("Infrastructure job failed for id %s", infrastructure_id)
        if db is not None:
            db.rollback()
        if infra is None:
            infra = db.get(Infrastructure, infrastructure_id)
        if infra is not None:
            infra.status = failure_status
            infra.last_error = str(exc)
            db.add(infra)
            db.commit()
    finally:
        db.close()


def provision_infrastructure_job(infrastructure_id: int) -> None:
    _run_infrastructure_job(
        infrastructure_id,
        provision_infrastructure,
        in_progress_status="provisioning",
        success_status="ready",
        failure_status="failed",
    )


def destroy_infrastructure_job(infrastructure_id: int) -> None:
    _run_infrastructure_job(
        infrastructure_id,
        destroy_infrastructure,
        in_progress_status="deleting",
        success_status="deleted",
        failure_status="delete_failed",
    )
