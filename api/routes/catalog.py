from fastapi import APIRouter

router = APIRouter()

APP_TEMPLATES = [
    {
        "id": "nginx-web",
        "name": "Static web app",
        "description": "Simple nginx web service for smoke tests and static frontend deployments.",
        "default_app_name": "web-app",
        "image": "nginx:1.25",
        "port": 80,
        "replicas": 2,
        "min_replicas": 1,
        "max_replicas": 5,
        "cpu_threshold": 70,
    },
    {
        "id": "fastapi-service",
        "name": "FastAPI service",
        "description": "Python API service with common HTTP defaults.",
        "default_app_name": "fastapi-service",
        "image": "tiangolo/uvicorn-gunicorn-fastapi:python3.11",
        "port": 80,
        "replicas": 2,
        "min_replicas": 1,
        "max_replicas": 6,
        "cpu_threshold": 70,
    },
    {
        "id": "node-api",
        "name": "Node.js API",
        "description": "Node HTTP API starter using a public demo image.",
        "default_app_name": "node-api",
        "image": "node:20-alpine",
        "port": 3000,
        "replicas": 2,
        "min_replicas": 1,
        "max_replicas": 6,
        "cpu_threshold": 70,
    },
    {
        "id": "worker",
        "name": "Background worker",
        "description": "Worker-style app with conservative scaling defaults.",
        "default_app_name": "worker-service",
        "image": "python:3.11-slim",
        "port": 8080,
        "replicas": 1,
        "min_replicas": 1,
        "max_replicas": 3,
        "cpu_threshold": 75,
    },
]

IMAGE_CATALOG = [
    {"label": "nginx 1.25", "image": "nginx:1.25", "port": 80},
    {"label": "httpd 2.4", "image": "httpd:2.4", "port": 80},
    {"label": "FastAPI gunicorn", "image": "tiangolo/uvicorn-gunicorn-fastapi:python3.11", "port": 80},
    {"label": "Node 20 Alpine", "image": "node:20-alpine", "port": 3000},
    {"label": "Python 3.11 Slim", "image": "python:3.11-slim", "port": 8080},
    {"label": "Redis 7 Alpine", "image": "redis:7-alpine", "port": 6379},
]


@router.get("")
def get_catalog():
    return {
        "apps": APP_TEMPLATES,
        "images": IMAGE_CATALOG,
    }
