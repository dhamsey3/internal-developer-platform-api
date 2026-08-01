import logging
import subprocess

import httpx

from app.config import settings
from database.models import Deployment
from services.providers.base import BaseDeploymentProvider

logger = logging.getLogger(__name__)

SANDBOX_TTL_SECONDS = 15 * 60
TERMINATED_LOG_MESSAGE = "Container terminated and logs purged."


def sandbox_container_names(deployment: Deployment) -> list[str]:
    names = [str(deployment.id)]
    if deployment.name:
        names.append(f"idp-{deployment.name}")
        names.append(deployment.name)
    return list(dict.fromkeys(names))


class VMRunnerProvider(BaseDeploymentProvider):
    def dispatch(self, deployment: Deployment) -> None:
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
            accepted_permissions = response.headers.get("x-accepted-github-permissions")
            if accepted_permissions:
                detail = f"{detail} Required permissions: {accepted_permissions}"
            raise RuntimeError(
                f"GitHub rejected the sandbox dispatch with status {response.status_code}: {detail}"
            )

    def get_logs(self, deployment: Deployment, tail: int = 100) -> list[str]:
        metadata = deployment.metadata_json or {}
        persisted_logs = metadata.get("logs") or ""
        if deployment.status in {"expired", "failed", "stopped"}:
            return persisted_logs.splitlines() or [TERMINATED_LOG_MESSAGE]

        container_id = metadata.get("runtime_id") or str(deployment.id)
        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", str(tail), container_id],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return persisted_logs.splitlines() or [TERMINATED_LOG_MESSAGE]

        output = "\n".join(part for part in [result.stdout, result.stderr] if part)
        if result.returncode == 0 and output:
            return output.splitlines()[-tail:]
        return persisted_logs.splitlines() or [TERMINATED_LOG_MESSAGE]

    def teardown(self, deployment: Deployment) -> None:
        for container_name in sandbox_container_names(deployment):
            try:
                subprocess.run(
                    ["docker", "rm", "-f", container_name],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
            except FileNotFoundError:
                logger.info("Docker CLI is not available while sweeping sandbox %s", deployment.id)
                return
            except subprocess.TimeoutExpired:
                logger.warning("Timed out removing sandbox container %s", container_name)
