from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


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
    namespace: str
    name: str
    service_name: str
    service_port: int = Field(..., ge=1, le=65535)
    host: str


class AutoscalingRequest(BaseModel):
    namespace: str = "default"
    deployment: str
    min_replicas: int = Field(..., ge=1)
    max_replicas: int = Field(..., ge=1)
    cpu_threshold: int = Field(..., ge=10, le=95)
