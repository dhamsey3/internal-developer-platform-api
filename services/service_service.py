from kubernetes import client
import logging
from app.config import settings
from services.kubernetes_client import get_k8s_client

logger = logging.getLogger(__name__)

def expose_service(namespace: str, name: str, port: int, target_port: int, type_: str = "ClusterIP"):
    if settings.KUBERNETES_DRY_RUN:
        logger.info("Dry run: service %s/%s would be exposed", namespace, name)
        return True
    try:
        v1, _, _, _ = get_k8s_client()
        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(name=name, namespace=namespace),
            spec=client.V1ServiceSpec(
                selector={"app": name},
                ports=[client.V1ServicePort(port=port, target_port=target_port)],
                type=type_
            )
        )
        v1.create_namespaced_service(namespace=namespace, body=service)
        logger.info("Service '%s' exposed on port %s in namespace '%s'.", name, port, namespace)
        return True
    except client.rest.ApiException as e:
        if e.status == 409:
            logger.info("Service '%s' already exists.", name)
            return True
        logger.error("Error exposing service: %s", e)
        return False
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return False
