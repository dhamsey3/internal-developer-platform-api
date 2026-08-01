from fastapi import APIRouter

router = APIRouter()

APP_TEMPLATES = [
    {
        "id": "deploy-demo-app",
        "name": "Deploy Demo App",
        "description": "Tiny public whoami service with root and /health endpoints for validating the deployment lifecycle.",
        "default_app_name": "idp-demo",
        "image": "mpepping/whoami:latest",
        "port": 8000,
        "replicas": 1,
        "min_replicas": 1,
        "max_replicas": 1,
        "cpu_threshold": 70,
    },
    {
        "id": "nginx-web",
        "name": "Nginx web app",
        "description": "Official nginx image pinned to a stable tag for a tiny static web app.",
        "default_app_name": "nginx-web",
        "image": "nginx:1.25-alpine",
        "port": 80,
        "replicas": 2,
        "min_replicas": 1,
        "max_replicas": 5,
        "cpu_threshold": 70,
    },
    {
        "id": "apache-web",
        "name": "Apache web app",
        "description": "Official Apache HTTP server image that works as a simple web deployment.",
        "default_app_name": "apache-web",
        "image": "httpd:2.4",
        "port": 80,
        "replicas": 2,
        "min_replicas": 1,
        "max_replicas": 5,
        "cpu_threshold": 70,
    },
    {
        "id": "whoami-api",
        "name": "Whoami API",
        "description": "Tiny HTTP app that returns request metadata; useful for smoke tests.",
        "default_app_name": "whoami-api",
        "image": "traefik/whoami:v1.10",
        "port": 80,
        "replicas": 2,
        "min_replicas": 1,
        "max_replicas": 6,
        "cpu_threshold": 70,
    },
    {
        "id": "hello-web",
        "name": "Hello web app",
        "description": "Nginx demo app that serves a simple hello page.",
        "default_app_name": "hello-web",
        "image": "nginxdemos/hello:plain-text",
        "port": 80,
        "replicas": 2,
        "min_replicas": 1,
        "max_replicas": 5,
        "cpu_threshold": 70,
    },
    {
        "id": "echo-server",
        "name": "Echo server",
        "description": "Small request/response test service for ingress and header debugging.",
        "default_app_name": "echo-server",
        "image": "ealen/echo-server:0.9.2",
        "port": 80,
        "replicas": 2,
        "min_replicas": 1,
        "max_replicas": 5,
        "cpu_threshold": 70,
    },
]

IMAGE_CATALOG = [
    {"label": "IDP demo app", "image": "mpepping/whoami:latest", "port": 8000},
    {"label": "nginx 1.25 alpine", "image": "nginx:1.25-alpine", "port": 80},
    {"label": "httpd 2.4", "image": "httpd:2.4", "port": 80},
    {"label": "traefik whoami", "image": "traefik/whoami:v1.10", "port": 80},
    {"label": "nginx hello demo", "image": "nginxdemos/hello:plain-text", "port": 80},
    {"label": "echo server", "image": "ealen/echo-server:0.9.2", "port": 80},
]


@router.get("")
def get_catalog():
    return {
        "apps": APP_TEMPLATES,
        "images": IMAGE_CATALOG,
    }
