from kubernetes import client
import logging
from app.config import settings
from services.kubernetes_client import get_k8s_client

logger = logging.getLogger(__name__)

def create_ingress(namespace: str, name: str, service_name: str, service_port: int, host: str):
    if settings.KUBERNETES_DRY_RUN:
        logger.info("Dry run: ingress %s/%s for host %s would be created", namespace, name, host)
        return True
    try:
        _, _, _, networking_v1 = get_k8s_client()
        ingress = client.V1Ingress(
            api_version="networking.k8s.io/v1",
            kind="Ingress",
            metadata=client.V1ObjectMeta(name=name, namespace=namespace),
            spec=client.V1IngressSpec(
                rules=[
                    client.V1IngressRule(
                        host=host,
                        http=client.V1HTTPIngressRuleValue(
                            paths=[
                                client.V1HTTPIngressPath(
                                    path="/",
                                    path_type="Prefix",
                                    backend=client.V1IngressBackend(
                                        service=client.V1IngressServiceBackend(
                                            name=service_name,
                                            port=client.V1ServiceBackendPort(number=service_port)
                                        )
                                    )
                                )
                            ]
                        )
                    )
                ]
            )
        )
        networking_v1.create_namespaced_ingress(namespace=namespace, body=ingress)
        logger.info("Ingress '%s' created for service '%s' on host '%s'.", name, service_name, host)
        return True
    except client.rest.ApiException as e:
        if e.status == 409:
            logger.info("Ingress '%s' already exists.", name)
            return True
        logger.error("Error creating ingress: %s", e)
        return False
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return False
