from fastapi import APIRouter, Depends, HTTPException

from api.schemas import AutoscalingRequest, IngressRequest, NamespaceRequest, ServiceExposeRequest
from auth.rbac import get_current_user
from services.autoscaling_service import create_hpa
from services.ingress_service import create_ingress
from services.k8s_service import create_namespace
from services.service_service import expose_service

router = APIRouter()

@router.post("/namespace/create")
def create_namespace_route(request: NamespaceRequest, current_user=Depends(get_current_user)):
    success = create_namespace(request.name)
    if success:
        return {"msg": f"Namespace '{request.name}' created."}
    raise HTTPException(status_code=500, detail="Failed to create namespace.")

@router.post("/service/expose")
def expose_service_route(request: ServiceExposeRequest, current_user=Depends(get_current_user)):
    success = expose_service(
        namespace=request.namespace,
        name=request.name,
        port=request.port,
        target_port=request.target_port,
        type_=request.type
    )
    if success:
        return {"msg": f"Service '{request.name}' exposed in namespace '{request.namespace}'."}
    raise HTTPException(status_code=500, detail="Failed to expose service.")

@router.post("/autoscaling/create")
def create_autoscaling_route(request: AutoscalingRequest, current_user=Depends(get_current_user)):
    success = create_hpa(
        namespace=request.namespace,
        deployment=request.deployment,
        min_replicas=request.min_replicas,
        max_replicas=request.max_replicas,
        cpu_threshold=request.cpu_threshold
    )
    if success:
        return {"msg": f"Autoscaling for {request.namespace}/{request.deployment} configured."}
    raise HTTPException(status_code=500, detail="Failed to configure autoscaling.")


@router.post("/ingress/create")
def create_ingress_route(request: IngressRequest, current_user=Depends(get_current_user)):
    success = create_ingress(
        namespace=request.namespace,
        name=request.name,
        service_name=request.service_name,
        service_port=request.service_port,
        host=request.host
    )
    if success:
        return {
            "msg": f"Ingress '{request.name}' created for service '{request.service_name}' on host '{request.host}'."
        }
    raise HTTPException(status_code=500, detail="Failed to create ingress.")
