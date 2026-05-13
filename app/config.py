from functools import lru_cache
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "Cloud Infrastructure Provisioning API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="local", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="APP_DEBUG")
    DATABASE_URL: str = Field(default="sqlite:///./idp.db", env="DATABASE_URL")
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    SECRET_KEY: str = Field(default="change-me-in-production", env="SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    AWS_REGION: str = Field(default="us-east-1", env="AWS_REGION")
    DEFAULT_INGRESS_DOMAIN: str = Field(default="apps.local", env="DEFAULT_INGRESS_DOMAIN")
    KUBERNETES_NAMESPACE_PREFIX: str = Field(default="tenant", env="KUBERNETES_NAMESPACE_PREFIX")
    KUBERNETES_DRY_RUN: bool = Field(default=False, env="KUBERNETES_DRY_RUN")
    TERRAFORM_DRY_RUN: bool = Field(default=True, env="TERRAFORM_DRY_RUN")
    TERRAFORM_STATE_BUCKET: str = Field(default="replace-me-terraform-state", env="TERRAFORM_STATE_BUCKET")
    TERRAFORM_LOCK_TABLE: str = Field(default="replace-me-terraform-locks", env="TERRAFORM_LOCK_TABLE")
    RATE_LIMIT_REQUESTS_PER_HOUR: int = Field(default=100, env="RATE_LIMIT_REQUESTS_PER_HOUR")
    REQUIRE_AUTH_FOR_PLATFORM_APIS: bool = Field(default=True, env="REQUIRE_AUTH_FOR_PLATFORM_APIS")

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
