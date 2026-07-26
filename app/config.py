from functools import lru_cache
from pydantic import BaseSettings, Field, validator


PRODUCTION_ENVIRONMENTS = {"production", "prod", "staging"}
DEFAULT_SECRET_KEY = "change-me-in-production"


class Settings(BaseSettings):
    PROJECT_NAME: str = "Internal Developer Platform API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="local", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="APP_DEBUG")
    DATABASE_URL: str = Field(default="sqlite:///./idp.db", env="DATABASE_URL")
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    SECRET_KEY: str = Field(default=DEFAULT_SECRET_KEY, env="SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    ALLOWED_ORIGINS: str = Field(default="http://localhost:8000,http://127.0.0.1:8000", env="ALLOWED_ORIGINS")
    ENABLE_PUBLIC_REGISTRATION: bool = Field(default=True, env="ENABLE_PUBLIC_REGISTRATION")
    AWS_REGION: str = Field(default="us-east-1", env="AWS_REGION")
    DEFAULT_INGRESS_DOMAIN: str = Field(default="apps.local", env="DEFAULT_INGRESS_DOMAIN")
    DEFAULT_DESTINATION_NAME: str = Field(default="home-vm", env="DEFAULT_DESTINATION_NAME")
    DEFAULT_DESTINATION_URL: str = Field(default="", env="DEFAULT_DESTINATION_URL")
    DEFAULT_RUNNER_LABEL: str = Field(default="idp-vm", env="DEFAULT_RUNNER_LABEL")
    DEFAULT_DESTINATION_ENABLED: bool = Field(default=True, env="DEFAULT_DESTINATION_ENABLED")
    GITHUB_REPOSITORY: str = Field(
        default="dhamsey3/internal-developer-platform-api",
        env="GITHUB_REPOSITORY",
    )
    GITHUB_DISPATCH_TOKEN: str = Field(default="", env="GITHUB_DISPATCH_TOKEN")
    DEPLOYMENT_CALLBACK_TOKEN: str = Field(default="", env="DEPLOYMENT_CALLBACK_TOKEN")
    KUBERNETES_NAMESPACE_PREFIX: str = Field(default="tenant", env="KUBERNETES_NAMESPACE_PREFIX")
    KUBERNETES_DRY_RUN: bool = Field(default=False, env="KUBERNETES_DRY_RUN")
    TERRAFORM_DRY_RUN: bool = Field(default=True, env="TERRAFORM_DRY_RUN")
    TERRAFORM_STATE_BUCKET: str = Field(default="replace-me-terraform-state", env="TERRAFORM_STATE_BUCKET")
    TERRAFORM_JOB_BACKEND: str = Field(default="background", env="TERRAFORM_JOB_BACKEND")
    TERRAFORM_JOB_REDIS_URL: str = Field(default="redis://localhost:6379/1", env="TERRAFORM_JOB_REDIS_URL")
    TERRAFORM_JOB_QUEUE_NAME: str = Field(default="terraform-jobs", env="TERRAFORM_JOB_QUEUE_NAME")
    RATE_LIMIT_REQUESTS_PER_HOUR: int = Field(default=100, env="RATE_LIMIT_REQUESTS_PER_HOUR")
    REQUIRE_AUTH_FOR_PLATFORM_APIS: bool = Field(default=True, env="REQUIRE_AUTH_FOR_PLATFORM_APIS")

    @validator("SECRET_KEY")
    def require_strong_secret_for_non_local(cls, value, values):
        environment = values.get("ENVIRONMENT", "local").lower()
        if environment in PRODUCTION_ENVIRONMENTS and (value == DEFAULT_SECRET_KEY or len(value) < 32):
            raise ValueError("SECRET_KEY must be changed to a random value of at least 32 characters")
        return value

    @validator("TERRAFORM_JOB_BACKEND")
    def validate_terraform_job_backend(cls, value):
        if value not in {"background", "redis"}:
            raise ValueError("TERRAFORM_JOB_BACKEND must be either 'background' or 'redis'")
        return value

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production_like(self) -> bool:
        return self.ENVIRONMENT.lower() in PRODUCTION_ENVIRONMENTS

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
