from fastapi import APIRouter

router = APIRouter()

APP_TEMPLATES = [
    {
        "id": "nginx-web",
        "name": "Nginx web app",
        "description": "Official nginx image that serves a default HTTP page on port 80.",
        "default_app_name": "nginx-web",
        "image": "nginx:1.25",
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
        "description": "Tiny HTTP app that returns request and container details.",
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
]

IMAGE_CATALOG = [
    {"label": "nginx 1.25", "image": "nginx:1.25", "port": 80},
    {"label": "httpd 2.4", "image": "httpd:2.4", "port": 80},
    {"label": "traefik whoami", "image": "traefik/whoami:v1.10", "port": 80},
    {"label": "nginx hello demo", "image": "nginxdemos/hello:plain-text", "port": 80},
]


@router.get("")
def get_catalog():
    return {
        "apps": APP_TEMPLATES,
        "images": IMAGE_CATALOG,
    }
