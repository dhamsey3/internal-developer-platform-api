import logging

from kubernetes.client import V1Namespace, V1ObjectMeta
from kubernetes.client.rest import ApiException

from app.config import settings
from services.kubernetes_client import get_k8s_client

logger = logging.getLogger(__name__)

def create_namespace(name: str):
    if settings.KUBERNETES_DRY_RUN:
        logger.info("Dry run: namespace %s would be created", name)
        return True
    try:
        v1, _, _, _ = get_k8s_client()
        ns = V1Namespace(metadata=V1ObjectMeta(name=name))
        v1.create_namespace(ns)
        logger.info("Namespace '%s' created.", name)
        return True
    except ApiException as e:
        if e.status == 409:
            logger.info("Namespace '%s' already exists.", name)
            return True
        logger.error("Error creating namespace: %s", e)
        return False
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return False
