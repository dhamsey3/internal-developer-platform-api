from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, regex=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)


class DestinationResponse(BaseModel):
    id: int
    name: str
    kind: str
    provider: str
    environment: str
    status: str
    config: Dict[str, Any]
    capabilities: List[str]
    is_default: bool
    readiness: Dict[str, Any] = {}

    class Config:
        orm_mode = True


class ApplicationCreateRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=63, regex=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    description: Optional[str] = Field(default=None, max_length=500)
    source_type: str = Field(..., regex=r"^(repository|container_image)$")
    repository_url: Optional[str] = Field(default=None, max_length=500)
    image: Optional[str] = Field(default=None, min_length=3, max_length=255)
    port: int = Field(default=80, ge=1, le=65535)
    destination_id: int = Field(..., ge=1)
    environment: str = Field(default="development", regex=r"^(development|staging|production)$")
    resource_requests: List[str] = Field(default_factory=list)

    @validator("repository_url", always=True)
    def repository_required_for_repository_source(cls, value, values):
        if values.get("source_type") == "repository" and not value:
            raise ValueError("repository_url is required for repository source")
        return value

    @validator("image", always=True)
    def image_required_for_container_source(cls, value, values):
        if values.get("source_type") == "container_image" and not value:
            raise ValueError("image is required for container image source")
        return value

    @validator("resource_requests")
    def supported_resource_requests(cls, value):
        supported = {"postgresql", "redis", "object_storage", "queue", "secrets"}
        unsupported = set(value) - supported
        if unsupported:
            raise ValueError(f"unsupported resources: {', '.join(sorted(unsupported))}")
        return list(dict.fromkeys(value))


class ApplicationResponse(BaseModel):
    id: int
    owner_id: int
    destination_id: int
    name: str
    description: Optional[str] = None
    source_type: str
    repository_url: Optional[str] = None
    image: Optional[str] = None
    port: int
    environment: str
    status: str
    resource_requests: List[str]
    metadata_json: Dict[str, Any] = {}
    created_at: datetime
    destination: Optional[DestinationResponse] = None

    class Config:
        orm_mode = True


class InfrastructureCreateRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=63, regex=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    cloud_provider: str = Field(default="aws", regex=r"^aws$")
    config: Dict[str, Any] = Field(default_factory=dict)


class InfrastructureResponse(BaseModel):
    id: int
    name: str
    cloud_provider: str
    status: str
    config: Dict[str, Any]
    last_error: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


class DeploymentCreateRequest(BaseModel):
    image: str = Field(..., min_length=3, max_length=255)
    name: str = Field(..., min_length=3, max_length=63, regex=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    namespace: Optional[str] = Field(default=None, max_length=63)
    port: int = Field(default=80, ge=1, le=65535)
    replicas: int = Field(default=1, ge=1, le=20)
    min_replicas: int = Field(default=1, ge=1, le=20)
    max_replicas: int = Field(default=3, ge=1, le=100)
    cpu_threshold: int = Field(default=70, ge=10, le=95)
    ingress_host: Optional[str] = Field(default=None, max_length=253)
    env: Dict[str, str] = Field(default_factory=dict)
    command: Optional[List[str]] = None
    args: Optional[List[str]] = None

    @validator("max_replicas")
    def max_gte_min(cls, value, values):
        min_replicas = values.get("min_replicas", 1)
        if value < min_replicas:
            raise ValueError("max_replicas must be greater than or equal to min_replicas")
        return value


class DeploymentResponse(BaseModel):
    id: int
    owner_id: int
    name: str
    namespace: str
    image: str
    port: int
    replicas: int
    ingress_host: Optional[str] = None
    url: Optional[str] = None
    status: str
    metadata_json: Dict[str, Any] = {}
    last_error: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


class NamespaceRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=63, regex=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")


class ServiceExposeRequest(BaseModel):
    namespace: str
    name: str
    port: int = Field(..., ge=1, le=65535)
    target_port: int = Field(..., ge=1, le=65535)
    type: str = Field(default="ClusterIP", regex=r"^(ClusterIP|NodePort|LoadBalancer)$")


class IngressRequest(BaseModel):
    namespace: str = Field(..., min_length=3, max_length=63, regex=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    name: str = Field(..., min_length=3, max_length=63, regex=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    service_name: str = Field(..., min_length=3, max_length=63, regex=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    service_port: int = Field(..., ge=1, le=65535)
    host: str = Field(..., min_length=3, max_length=253, regex=r"^[a-z0-9]([-a-z0-9.]*[a-z0-9])?$")


class AutoscalingRequest(BaseModel):
    namespace: str = Field(default="default", min_length=3, max_length=63, regex=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    deployment: str = Field(..., min_length=3, max_length=63, regex=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    min_replicas: int = Field(..., ge=1)
    max_replicas: int = Field(..., ge=1)
    cpu_threshold: int = Field(..., ge=10, le=95)
