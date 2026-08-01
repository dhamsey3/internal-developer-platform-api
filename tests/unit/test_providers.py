from database.models import Deployment
from services.providers.factory import deployment_provider_type, get_provider
from services.providers.vm_docker import VMRunnerProvider


def test_provider_factory_returns_vm_docker_provider():
    assert isinstance(get_provider("vm_docker"), VMRunnerProvider)


def test_provider_factory_rejects_unknown_provider():
    try:
        get_provider("not-real")
    except ValueError as exc:
        assert "Unsupported deployment provider" in str(exc)
    else:
        raise AssertionError("Expected unknown provider to be rejected")


def test_deployment_provider_type_defaults_to_vm_docker():
    deployment = Deployment(metadata_json={})

    assert deployment_provider_type(deployment) == "vm_docker"
