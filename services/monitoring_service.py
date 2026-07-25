import logging
from app.config import settings
from services.kubernetes_client import get_k8s_client

logger = logging.getLogger(__name__)

def get_cluster_health():
    if settings.KUBERNETES_DRY_RUN:
        return {"status": "not_configured", "mode": "dry-run", "nodes": 0, "ready_nodes": 0}
    try:
        v1, _, _, _ = get_k8s_client()
        nodes = v1.list_node()
        ready_nodes = 0
        for node in nodes.items:
            for condition in node.status.conditions:
                if condition.type == "Ready" and condition.status == "True":
                    ready_nodes += 1
                    break
        status = "healthy" if ready_nodes == len(nodes.items) else "degraded"
        return {"status": status, "nodes": len(nodes.items), "ready_nodes": ready_nodes}
    except Exception as e:
        logger.error("Error checking cluster health: %s", e)
        return {"status": "error", "detail": str(e)}

def get_pod_logs(namespace: str, pod: str):
    if settings.KUBERNETES_DRY_RUN:
        return {"pod": pod, "namespace": namespace, "logs": "dry-run: Kubernetes API not called"}
    try:
        v1, _, _, _ = get_k8s_client()
        logs = v1.read_namespaced_pod_log(name=pod, namespace=namespace)
        return {"pod": pod, "logs": logs}
    except Exception as e:
        logger.error("Error fetching logs for pod %s: %s", pod, e)
        return {"pod": pod, "logs": str(e)}
