from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from database.models import Deployment
from services.providers.factory import get_deployment_provider
from services.providers.vm_docker import SANDBOX_TTL_SECONDS


SANDBOX_TEMPLATES = {
    "whoami": {
        "image": "mpepping/whoami:latest",
        "container_port": 8000,
    },
    "nginx": {
        "image": "nginx:1.25-alpine",
        "container_port": 80,
    },
}


# Sandboxes in these states may have a container on the runner. Expired-but-unswept
# ones still count: their container is running until the sweeper removes it.
ACTIVE_SANDBOX_STATUSES = ("queued", "deploying", "running")
MIN_RETRY_AFTER_SECONDS = 30


class SandboxCapacityError(Exception):
    def __init__(self, message: str, retry_after_seconds: int):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def ensure_sandbox_capacity(db: Session, now: datetime) -> None:
    """Anyone can start a sandbox without logging in, so cap how many run at once."""
    if settings.MAX_ACTIVE_SANDBOXES == 0:
        raise SandboxCapacityError("Sandbox demos are disabled", retry_after_seconds=3600)
    expiries = [
        row[0]
        for row in db.query(Deployment.expires_at).filter(
            Deployment.is_sandbox.is_(True),
            Deployment.status.in_(ACTIVE_SANDBOX_STATUSES),
        )
    ]
    if len(expiries) < settings.MAX_ACTIVE_SANDBOXES:
        return
    # SQLite hands back naive datetimes; they were stored as UTC.
    known = [expiry if expiry.tzinfo else expiry.replace(tzinfo=timezone.utc) for expiry in expiries if expiry]
    seconds_until_free = int((min(known) - now).total_seconds()) if known else 0
    raise SandboxCapacityError(
        "All sandbox slots are in use. Try again in a few minutes.",
        retry_after_seconds=max(seconds_until_free, MIN_RETRY_AFTER_SECONDS),
    )


def sandbox_template(name: str) -> dict[str, Any]:
    template = SANDBOX_TEMPLATES.get(name)
    if template is None:
        raise ValueError("Unsupported sandbox template")
    return template


def sandbox_host_port(deployment_id: int) -> int:
    return 20000 + deployment_id


def create_sandbox_deployment(db: Session, template_name: str) -> Deployment:
    template = sandbox_template(template_name)
    now = datetime.now(timezone.utc)
    ensure_sandbox_capacity(db, now)
    deployment = Deployment(
        owner_id=0,
        name=f"sandbox-{template_name}",
        namespace="sandbox",
        image=template["image"],
        port=0,
        container_port=template["container_port"],
        replicas=1,
        status="queued",
        expires_at=now + timedelta(seconds=SANDBOX_TTL_SECONDS),
        is_sandbox=True,
        metadata_json={
            "template": template_name,
            "provider": "vm_docker",
            "ttl_seconds": SANDBOX_TTL_SECONDS,
            "queued_at": now.isoformat(),
        },
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    host_port = sandbox_host_port(deployment.id)
    deployment.name = f"sandbox-{template_name}-{deployment.id}"
    deployment.port = host_port
    deployment.metadata_json = {
        **(deployment.metadata_json or {}),
        "host_port": host_port,
    }
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    return deployment


def dispatch_sandbox_deployment(deployment: Deployment) -> None:
    get_deployment_provider(deployment).dispatch(deployment)
