from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from database.models import Destination


@dataclass(frozen=True)
class DestinationReadiness:
    ready: bool
    checks: dict[str, bool]
    missing: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {"ready": self.ready, "checks": self.checks, "missing": self.missing}


class DestinationAdapter:
    kind = "unsupported"

    def validate(self, destination: Destination) -> DestinationReadiness:
        return DestinationReadiness(False, {"adapter": False}, ["A destination adapter is not available"])


class LinuxDockerAdapter(DestinationAdapter):
    kind = "linux_docker"

    def validate(self, destination: Destination) -> DestinationReadiness:
        config = destination.config or {}
        checks = {
            "enabled": bool(config.get("enabled")),
            "runner_label": bool(config.get("runner_label")),
            "github_repository": bool(config.get("github_repository")),
            "deployment_workflow": bool(config.get("deployment_workflow")),
        }
        missing_labels = {
            "enabled": "Enable this destination",
            "runner_label": "Configure a dedicated GitHub runner label",
            "github_repository": "Configure the GitHub repository used for workflow dispatch",
            "deployment_workflow": "Configure an application deployment workflow",
        }
        missing = [missing_labels[key] for key, passed in checks.items() if not passed]
        return DestinationReadiness(all(checks.values()), checks, missing)


class SetupRequiredAdapter(DestinationAdapter):
    def __init__(self, requirement: str):
        self.requirement = requirement

    def validate(self, destination: Destination) -> DestinationReadiness:
        return DestinationReadiness(False, {"configured": False}, [self.requirement])


ADAPTERS = {
    "linux_docker": LinuxDockerAdapter(),
    "local_docker": SetupRequiredAdapter("Install and connect a local platform agent"),
    "aws_ecs": SetupRequiredAdapter("Connect an AWS account with GitHub OIDC"),
    "existing_kubernetes": SetupRequiredAdapter("Register a Kubernetes deployment identity"),
    "azure_container_apps": SetupRequiredAdapter("Connect an Azure subscription"),
    "gcp_cloud_run": SetupRequiredAdapter("Connect a Google Cloud project"),
}

SUPPORTED_RESOURCES = {
    "linux_docker": {"postgresql", "secrets"},
}


def destination_readiness(destination: Destination) -> dict[str, Any]:
    adapter = ADAPTERS.get(destination.kind, DestinationAdapter())
    return adapter.validate(destination).as_dict()


def seed_destinations(db: Session) -> None:
    defaults = [
        {
            "name": settings.DEFAULT_DESTINATION_NAME,
            "kind": "linux_docker",
            "provider": "existing_server",
            "environment": "development",
            "config": {
                "enabled": settings.DEFAULT_DESTINATION_ENABLED,
                "runner_label": settings.DEFAULT_RUNNER_LABEL,
                "base_url": settings.DEFAULT_DESTINATION_URL,
                "github_repository": settings.GITHUB_REPOSITORY,
                "deployment_workflow": bool(
                    settings.GITHUB_DISPATCH_TOKEN and settings.DEPLOYMENT_CALLBACK_TOKEN
                ),
            },
            "capabilities": ["containers", "persistent_storage", "postgresql", "secrets"],
            "is_default": True,
        },
        {
            "name": "local-docker",
            "kind": "local_docker",
            "provider": "local",
            "environment": "development",
            "config": {},
            "capabilities": ["containers"],
            "is_default": False,
        },
        {
            "name": "aws-sandbox",
            "kind": "aws_ecs",
            "provider": "aws",
            "environment": "development",
            "config": {},
            "capabilities": ["containers", "managed_databases", "object_storage", "queues"],
            "is_default": False,
        },
    ]
    for item in defaults:
        destination = db.query(Destination).filter(Destination.name == item["name"]).first()
        if destination is None:
            destination = Destination(**item)
            db.add(destination)
        elif destination.is_default and destination.kind == "linux_docker":
            config = destination.config or {}
            destination.config = {
                **config,
                "enabled": settings.DEFAULT_DESTINATION_ENABLED,
                "runner_label": settings.DEFAULT_RUNNER_LABEL,
                "base_url": settings.DEFAULT_DESTINATION_URL,
                "github_repository": settings.GITHUB_REPOSITORY,
                "deployment_workflow": bool(
                    settings.GITHUB_DISPATCH_TOKEN and settings.DEPLOYMENT_CALLBACK_TOKEN
                ),
            }
            destination.capabilities = item["capabilities"]
            db.add(destination)
    db.commit()


def refresh_destination_status(destination: Destination) -> dict[str, Any]:
    readiness = destination_readiness(destination)
    destination.status = "ready" if readiness["ready"] else "setup_required"
    return readiness


def resources_readiness(destination: Destination, requested: list[str]) -> dict[str, dict[str, Any]]:
    supported = SUPPORTED_RESOURCES.get(destination.kind, set())
    return {
        resource: {
            "ready": resource in supported,
            "message": (
                "Provided by the destination deployment workflow"
                if resource in supported
                else "Resource provisioning is not configured for this destination"
            ),
        }
        for resource in requested
    }
