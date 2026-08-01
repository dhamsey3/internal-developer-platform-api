from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

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
