from kubernetes import client, config
import os
import logging

logger = logging.getLogger(__name__)

def get_k8s_client():
    try:
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes config")
        else:
            config.load_kube_config()
            logger.info("Loaded local kubeconfig")
        return client.CoreV1Api(), client.AppsV1Api(), client.AutoscalingV1Api(), client.NetworkingV1Api()
    except Exception as e:
        logger.error(f"Failed to load Kubernetes config: {e}")
        raise
