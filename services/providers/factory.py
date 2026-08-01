from database.models import Deployment
from services.providers.base import BaseDeploymentProvider
from services.providers.vm_docker import VMRunnerProvider

DEFAULT_PROVIDER_TYPE = "vm_docker"

PROVIDERS: dict[str, type[BaseDeploymentProvider]] = {
    "vm_docker": VMRunnerProvider,
}


def deployment_provider_type(deployment: Deployment) -> str:
    metadata = deployment.metadata_json or {}
    return metadata.get("provider") or DEFAULT_PROVIDER_TYPE


def get_provider(provider_type: str = DEFAULT_PROVIDER_TYPE) -> BaseDeploymentProvider:
    provider_class = PROVIDERS.get(provider_type)
    if provider_class is None:
        raise ValueError(f"Unsupported deployment provider: {provider_type}")
    return provider_class()


def get_deployment_provider(deployment: Deployment) -> BaseDeploymentProvider:
    return get_provider(deployment_provider_type(deployment))
