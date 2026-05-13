from kubernetes import client
import logging
from app.config import settings
from services.kubernetes_client import get_k8s_client

logger = logging.getLogger(__name__)

def create_hpa(namespace: str, deployment: str, min_replicas: int, max_replicas: int, cpu_threshold: int):
    if settings.KUBERNETES_DRY_RUN:
        logger.info("Dry run: hpa %s/%s would be created", namespace, deployment)
        return True
    try:
        _, _, autoscaling_v1, _ = get_k8s_client()
        hpa = client.V1HorizontalPodAutoscaler(
            api_version="autoscaling/v1",
            kind="HorizontalPodAutoscaler",
            metadata=client.V1ObjectMeta(name=deployment, namespace=namespace),
            spec=client.V1HorizontalPodAutoscalerSpec(
                scale_target_ref=client.V1CrossVersionObjectReference(
                    api_version="apps/v1",
                    kind="Deployment",
                    name=deployment
                ),
                min_replicas=min_replicas,
                max_replicas=max_replicas,
                target_cpu_utilization_percentage=cpu_threshold
            )
        )
        autoscaling_v1.create_namespaced_horizontal_pod_autoscaler(namespace=namespace, body=hpa)
        logger.info("HPA for deployment '%s' created in namespace '%s'.", deployment, namespace)
        return True
    except client.rest.ApiException as e:
        if e.status == 409:
            logger.info("HPA for '%s' already exists.", deployment)
            return True
        logger.error("Error creating HPA: %s", e)
        return False
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return False
