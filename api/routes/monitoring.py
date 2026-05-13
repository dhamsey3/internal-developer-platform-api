from fastapi import APIRouter, Depends, Query
from services.monitoring_service import get_cluster_health, get_pod_logs
from fastapi import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from auth.rbac import get_current_user

router = APIRouter()

@router.get("/cluster/health")
def cluster_health(current_user=Depends(get_current_user)):
    return get_cluster_health()

@router.get("/metrics")
def metrics(current_user=Depends(get_current_user)):
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@router.get("/logs/{pod}")
def logs(pod: str, namespace: str = Query("default"), current_user=Depends(get_current_user)):
    return get_pod_logs(namespace, pod)
