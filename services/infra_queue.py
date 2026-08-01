import json
import logging
from datetime import datetime, timezone
from typing import Optional, Union
from uuid import uuid4

import redis
from fastapi import BackgroundTasks
from redis.exceptions import RedisError

from app.config import settings
from services.infra_jobs import destroy_infrastructure_job, provision_infrastructure_job

logger = logging.getLogger(__name__)

SUPPORTED_ACTIONS = {"provision", "destroy"}


class InfrastructureQueueError(RuntimeError):
    pass


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(settings.TERRAFORM_JOB_REDIS_URL, socket_connect_timeout=2, socket_timeout=2)


def enqueue_infrastructure_job(
    action: str,
    infrastructure_id: int,
    background_tasks: Optional[BackgroundTasks] = None,
) -> str:
    if action not in SUPPORTED_ACTIONS:
        raise InfrastructureQueueError(f"Unsupported infrastructure job action: {action}")

    job_id = str(uuid4())
    payload = {
        "id": job_id,
        "action": action,
        "infrastructure_id": infrastructure_id,
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
    }

    if settings.TERRAFORM_JOB_BACKEND == "background":
        if background_tasks is None:
            raise InfrastructureQueueError("BackgroundTasks is required for background job backend")
        job = provision_infrastructure_job if action == "provision" else destroy_infrastructure_job
        background_tasks.add_task(job, infrastructure_id)
        return job_id

    if settings.TERRAFORM_JOB_BACKEND != "redis":
        raise InfrastructureQueueError("TERRAFORM_JOB_BACKEND must be either 'redis' or 'background'")

    try:
        _redis_client().rpush(settings.TERRAFORM_JOB_QUEUE_NAME, json.dumps(payload))
    except RedisError as exc:
        logger.exception("Failed to enqueue infrastructure job")
        raise InfrastructureQueueError("Infrastructure job queue is unavailable") from exc
    return job_id


def decode_job(raw_payload: Union[bytes, str]) -> dict:
    if isinstance(raw_payload, bytes):
        raw_payload = raw_payload.decode("utf-8")
    payload = json.loads(raw_payload)
    if payload.get("action") not in SUPPORTED_ACTIONS:
        raise InfrastructureQueueError("Queued infrastructure job has an unsupported action")
    if not isinstance(payload.get("infrastructure_id"), int):
        raise InfrastructureQueueError("Queued infrastructure job is missing infrastructure_id")
    return payload
