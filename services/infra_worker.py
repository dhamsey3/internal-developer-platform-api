import logging
import signal
from typing import Any

from redis.exceptions import RedisError

from app.config import settings
from app.logger import setup_logging
from services.infra_jobs import destroy_infrastructure_job, provision_infrastructure_job
from services.infra_queue import InfrastructureQueueError, _redis_client, decode_job

logger = logging.getLogger(__name__)
_shutdown_requested = False


def _handle_shutdown(signum: int, frame: Any) -> None:
    global _shutdown_requested
    _shutdown_requested = True
    logger.info("Terraform worker shutdown requested")


def process_job(payload: dict) -> None:
    action = payload["action"]
    infrastructure_id = payload["infrastructure_id"]
    logger.info("Processing infrastructure job %s for id %s", action, infrastructure_id)
    if action == "provision":
        provision_infrastructure_job(infrastructure_id)
    elif action == "destroy":
        destroy_infrastructure_job(infrastructure_id)
    else:
        raise InfrastructureQueueError("Unsupported infrastructure job action")


def run_worker() -> None:
    setup_logging()
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)
    client = _redis_client()
    logger.info("Terraform worker listening on Redis queue '%s'", settings.TERRAFORM_JOB_QUEUE_NAME)

    while not _shutdown_requested:
        try:
            item = client.blpop(settings.TERRAFORM_JOB_QUEUE_NAME, timeout=5)
            if item is None:
                continue
            _, raw_payload = item
            process_job(decode_job(raw_payload))
        except InfrastructureQueueError:
            logger.exception("Invalid infrastructure job payload")
        except RedisError:
            logger.exception("Redis error while reading infrastructure job queue")
        except Exception:
            logger.exception("Unhandled infrastructure worker error")


if __name__ == "__main__":
    run_worker()
