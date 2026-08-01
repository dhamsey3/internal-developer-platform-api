import asyncio
import shutil
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from api.routes import applications, auth, catalog, deployments, destinations, infrastructure, kubernetes, monitoring
from api.routes import sandbox
from auth.rate_limit import rate_limiter
from app.config import settings
from app.logger import setup_logging
from app.security import SecurityHeadersMiddleware
from database.session import SessionLocal, init_db
from services.destination_service import seed_destinations
from services.sandbox_sweeper import sandbox_sweeper_loop

setup_logging()


def startup_tasks():
    init_db()
    db = SessionLocal()
    try:
        seed_destinations(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup_tasks()
    sweeper_task = None
    if settings.ENABLE_SANDBOX_SWEEPER:
        sweeper_task = asyncio.create_task(sandbox_sweeper_loop())
    try:
        yield
    finally:
        if sweeper_task is not None:
            sweeper_task.cancel()
            try:
                await sweeper_task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Developer hub for cataloging applications, dependencies, deployment "
        "destinations, and runtime operations."
    ),
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


app.include_router(auth.router, prefix="/auth", tags=["auth"], dependencies=[Depends(rate_limiter)])
app.include_router(
    infrastructure.router,
    prefix="/infrastructure",
    tags=["infrastructure"],
    dependencies=[Depends(rate_limiter)],
)
app.include_router(
    applications.router,
    prefix="/applications",
    tags=["applications"],
    dependencies=[Depends(rate_limiter)],
)
app.include_router(
    destinations.router,
    prefix="/destinations",
    tags=["destinations"],
    dependencies=[Depends(rate_limiter)],
)
app.include_router(
    deployments.router,
    prefix="/deployments",
    tags=["deployments"],
    dependencies=[Depends(rate_limiter)],
)
app.include_router(sandbox.router, prefix="/sandbox", tags=["sandbox"], dependencies=[Depends(rate_limiter)])
app.include_router(catalog.router, prefix="/catalog", tags=["catalog"], dependencies=[Depends(rate_limiter)])
app.include_router(kubernetes.router, prefix="/kubernetes", tags=["kubernetes"], dependencies=[Depends(rate_limiter)])
app.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"], dependencies=[Depends(rate_limiter)])
app.mount("/dashboard", StaticFiles(directory="web", html=True), name="dashboard")


@app.get("/healthz")
def health_check():
    return {"status": "ok"}


@app.get("/readyz")
def readiness_check():
    checks = {
        "database": False,
        "terraform": settings.TERRAFORM_DRY_RUN or shutil.which("terraform") is not None,
        "aws_cli": settings.TERRAFORM_DRY_RUN or shutil.which("aws") is not None,
    }
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except SQLAlchemyError:
        checks["database"] = False
    finally:
        db.close()

    if not all(checks.values()):
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "checks": checks},
        )
    return {
        "status": "ready",
        "environment": settings.ENVIRONMENT,
        "kubernetes_dry_run": settings.KUBERNETES_DRY_RUN,
        "terraform_dry_run": settings.TERRAFORM_DRY_RUN,
        "checks": checks,
    }


@app.get("/")
def root():
    return RedirectResponse(url="/dashboard/")
