from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from database.models import Deployment


SANDBOX_TTL_SECONDS = 15 * 60
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
    if not settings.GITHUB_DISPATCH_TOKEN:
        raise ValueError("GitHub sandbox dispatch is not configured")
    response = httpx.post(
        f"https://api.github.com/repos/{settings.GITHUB_REPOSITORY}/dispatches",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {settings.GITHUB_DISPATCH_TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={
            "event_type": "deploy_sandbox",
            "client_payload": {
                "deployment_id": str(deployment.id),
                "name": deployment.name,
                "image": deployment.image,
                "container_port": str(deployment.container_port),
                "host_port": str(deployment.port),
                "ttl_seconds": str(SANDBOX_TTL_SECONDS),
            },
        },
        timeout=20,
    )
    if response.status_code != 204:
        detail = response.text[:500] if response.text else "no response body"
        raise RuntimeError(
            f"GitHub rejected the sandbox dispatch with status {response.status_code}: {detail}"
        )
