import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from database.models import Deployment
from database.session import SessionLocal
from services.providers.factory import get_deployment_provider
from services.providers.vm_docker import sandbox_container_names as vm_docker_container_names

logger = logging.getLogger(__name__)

SANDBOX_SWEEP_INTERVAL_SECONDS = 60
EXPIRED_SANDBOX_STATUSES = ("queued", "running")


def sandbox_container_names(deployment: Deployment) -> list[str]:
    return vm_docker_container_names(deployment)


def remove_sandbox_container(deployment: Deployment) -> None:
    get_deployment_provider(deployment).teardown(deployment)


def sweep_expired_sandboxes(db: Session, now: Optional[datetime] = None) -> int:
    now = now or datetime.now(timezone.utc)
    expired = (
        db.query(Deployment)
        .filter(
            Deployment.is_sandbox.is_(True),
            Deployment.status.in_(EXPIRED_SANDBOX_STATUSES),
            Deployment.expires_at.isnot(None),
            Deployment.expires_at < now,
        )
        .all()
    )
    swept = 0
    for deployment in expired:
        try:
            remove_sandbox_container(deployment)
        except Exception as exc:
            # Leave it active so the next sweep retries; marking it expired
            # here would leave the container running with nothing tracking it.
            logger.warning("Could not tear down sandbox %s: %s", deployment.id, exc)
            deployment.metadata_json = {
                **(deployment.metadata_json or {}),
                "teardown_error": str(exc),
                "teardown_attempted_at": now.isoformat(),
            }
            db.add(deployment)
            continue
        deployment.status = "expired"
        deployment.metadata_json = {
            **(deployment.metadata_json or {}),
            "swept_at": now.isoformat(),
        }
        db.add(deployment)
        swept += 1
    if expired:
        db.commit()
    return swept


async def sandbox_sweeper_loop(interval_seconds: int = SANDBOX_SWEEP_INTERVAL_SECONDS) -> None:
    while True:
        db = SessionLocal()
        try:
            sweep_expired_sandboxes(db)
        except Exception:
            logger.exception("Sandbox sweeper failed")
        finally:
            db.close()
        await asyncio.sleep(interval_seconds)
