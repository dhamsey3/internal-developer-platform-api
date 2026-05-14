from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from api.routes import auth, infrastructure, deployments, kubernetes, monitoring
from auth.rate_limit import rate_limiter
from app.config import settings
from app.logger import setup_logging
from database.session import init_db

setup_logging()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Internal Developer Platform API for infrastructure provisioning "
        "and Kubernetes application deployment."
    ),
)


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(auth.router, prefix="/auth", tags=["auth"], dependencies=[Depends(rate_limiter)])
app.include_router(
    infrastructure.router,
    prefix="/infrastructure",
    tags=["infrastructure"],
    dependencies=[Depends(rate_limiter)],
)
app.include_router(
    deployments.router,
    prefix="/deployments",
    tags=["deployments"],
    dependencies=[Depends(rate_limiter)],
)
app.include_router(kubernetes.router, prefix="/kubernetes", tags=["kubernetes"], dependencies=[Depends(rate_limiter)])
app.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"], dependencies=[Depends(rate_limiter)])
app.include_router(kubernetes.router, tags=["kubernetes"], dependencies=[Depends(rate_limiter)])
app.include_router(monitoring.router, tags=["monitoring"], dependencies=[Depends(rate_limiter)])
app.mount("/dashboard", StaticFiles(directory="web", html=True), name="dashboard")


@app.get("/healthz")
def health_check():
    return {"status": "ok"}


@app.get("/readyz")
def readiness_check():
    return {
        "status": "ready",
        "environment": settings.ENVIRONMENT,
        "kubernetes_dry_run": settings.KUBERNETES_DRY_RUN,
        "terraform_dry_run": settings.TERRAFORM_DRY_RUN,
    }


@app.get("/")
def root():
    return RedirectResponse(url="/dashboard/")
