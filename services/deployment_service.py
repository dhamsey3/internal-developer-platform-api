import logging
from typing import Dict, Optional

from kubernetes import client
from kubernetes.client.rest import ApiException
from sqlalchemy.orm import Session

from app.config import settings
from api.schemas import DeploymentCreateRequest
from database.models import Deployment, User
from services.kubernetes_client import get_k8s_client
from services.autoscaling_service import create_hpa
from services.ingress_service import create_ingress
from services.k8s_service import create_namespace
from services.service_service import expose_service

logger = logging.getLogger(__name__)


def _default_namespace(user: User, name: str) -> str:
    return f"{settings.KUBERNETES_NAMESPACE_PREFIX}-{user.id}-{name}"[:63].rstrip("-")


def _default_host(user: User, name: str) -> str:
    return f"{name}-{user.id}.{settings.DEFAULT_INGRESS_DOMAIN}"


def validate_docker_image(image: str) -> None:
    if " " in image or image.startswith(":") or image.endswith(":"):
        raise ValueError("Invalid Docker image reference")
    if "/" not in image and ":" not in image:
        # Still allow official images, but force explicit tags in production.
        logger.warning("Image '%s' has no registry or tag; use immutable tags in production", image)


def create_secret(namespace: str, name: str, data: Dict[str, str]) -> bool:
    if not data:
        return True
    if settings.KUBERNETES_DRY_RUN:
        logger.info("Dry run: secret %s/%s would be created", namespace, name)
        return True
    try:
        v1, _, _, _ = get_k8s_client()
        secret = client.V1Secret(
            api_version="v1",
            kind="Secret",
            metadata=client.V1ObjectMeta(name=name, namespace=namespace),
            type="Opaque",
            string_data=data,
        )
        v1.create_namespaced_secret(namespace=namespace, body=secret)
        return True
    except ApiException as exc:
        if exc.status == 409:
            logger.info("Secret '%s' already exists.", name)
            return True
        logger.error("Error creating secret: %s", exc)
        return False


def create_deployment(
    namespace: str,
    name: str,
    image: str,
    port: int = 80,
    replicas: int = 1,
    secret_name: Optional[str] = None,
    command: Optional[list[str]] = None,
    args: Optional[list[str]] = None,
):
    if settings.KUBERNETES_DRY_RUN:
        logger.info("Dry run: deployment %s/%s with image %s would be created", namespace, name, image)
        return True
    try:
        _, apps_v1, _, _ = get_k8s_client()
        container = client.V1Container(
            name=name,
            image=image,
            ports=[client.V1ContainerPort(container_port=port)],
            env_from=[
                client.V1EnvFromSource(secret_ref=client.V1SecretEnvSource(name=secret_name))
            ] if secret_name else None,
            command=command,
            args=args,
        )
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"app": name}),
            spec=client.V1PodSpec(containers=[container])
        )
        spec = client.V1DeploymentSpec(
            replicas=replicas,
            template=template,
            selector={'matchLabels': {'app': name}}
        )
        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=name, namespace=namespace),
            spec=spec
        )
        apps_v1.create_namespaced_deployment(namespace=namespace, body=deployment)
        logger.info("Deployment '%s' created in namespace '%s'.", name, namespace)
        return True
    except ApiException as e:
        if e.status == 409:
            logger.info("Deployment '%s' already exists.", name)
            return True
        logger.error("Error creating deployment: %s", e)
        return False
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return False


def delete_kubernetes_deployment(namespace: str, name: str) -> None:
    if settings.KUBERNETES_DRY_RUN:
        logger.info("Dry run: Kubernetes resources for %s/%s would be deleted", namespace, name)
        return
    v1, apps_v1, autoscaling_v1, networking_v1 = get_k8s_client()
    for delete_call, kwargs in [
        (networking_v1.delete_namespaced_ingress, {"name": name, "namespace": namespace}),
        (autoscaling_v1.delete_namespaced_horizontal_pod_autoscaler, {"name": name, "namespace": namespace}),
        (v1.delete_namespaced_service, {"name": name, "namespace": namespace}),
        (apps_v1.delete_namespaced_deployment, {"name": name, "namespace": namespace}),
        (v1.delete_namespaced_secret, {"name": f"{name}-env", "namespace": namespace}),
    ]:
        try:
            delete_call(**kwargs)
        except ApiException as exc:
            if exc.status != 404:
                raise


def get_kubernetes_deployment_status(namespace: str, name: str) -> Dict[str, Optional[int]]:
    if settings.KUBERNETES_DRY_RUN:
        return {"available_replicas": 1, "ready_replicas": 1, "replicas": 1}
    _, apps_v1, _, _ = get_k8s_client()
    deployment = apps_v1.read_namespaced_deployment(name=name, namespace=namespace)
    status = deployment.status
    return {
        "available_replicas": status.available_replicas or 0,
        "ready_replicas": status.ready_replicas or 0,
        "replicas": status.replicas or 0,
    }


def provision_application(db: Session, user: User, request: DeploymentCreateRequest) -> Deployment:
    validate_docker_image(request.image)
    namespace = request.namespace or _default_namespace(user, request.name)
    ingress_host = request.ingress_host or _default_host(user, request.name)
    deployment = Deployment(
        owner_id=user.id,
        name=request.name,
        namespace=namespace,
        image=request.image,
        port=request.port,
        replicas=request.replicas,
        ingress_host=ingress_host,
        url=f"https://{ingress_host}",
        status="provisioning",
        metadata_json={
            "env_keys": sorted(request.env.keys()),
            "command": request.command,
            "args": request.args,
        },
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)

    try:
        steps = [
            create_namespace(namespace),
            create_secret(namespace, f"{request.name}-env", request.env),
            create_deployment(
                namespace,
                request.name,
                request.image,
                request.port,
                request.replicas,
                secret_name=f"{request.name}-env" if request.env else None,
                command=request.command,
                args=request.args,
            ),
            expose_service(namespace, request.name, 80, request.port),
            create_ingress(namespace, request.name, request.name, 80, ingress_host),
            create_hpa(namespace, request.name, request.min_replicas, request.max_replicas, request.cpu_threshold),
        ]
        if not all(steps):
            raise RuntimeError("One or more Kubernetes resources failed to apply")
        deployment.status = "running"
        deployment.metadata_json = {
            **(deployment.metadata_json or {}),
            "autoscaling": {
                "min_replicas": request.min_replicas,
                "max_replicas": request.max_replicas,
                "cpu_threshold": request.cpu_threshold,
            },
            "dry_run": settings.KUBERNETES_DRY_RUN,
        }
    except Exception as exc:
        logger.exception("Deployment provisioning failed")
        deployment.status = "failed"
        deployment.last_error = str(exc)
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    return deployment
