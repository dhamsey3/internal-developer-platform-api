from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/readiness")
def system_readiness():
    return {
        "dispatch_token_present": bool(settings.GITHUB_DISPATCH_TOKEN),
        "callback_token_present": bool(settings.DEPLOYMENT_CALLBACK_TOKEN),
        "preview_routing_configured": bool(settings.PREVIEW_ROUTING_ENABLED),
    }
