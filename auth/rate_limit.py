import redis
from fastapi import Request, HTTPException
from app.config import settings

try:
    r = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=0.2, socket_timeout=0.2)
except Exception:
    r = None


def rate_limiter(request: Request):
    if r is None:
        return
    ip = request.client.host
    key = f"rate_limit:{ip}"
    try:
        count = r.get(key)
        if count and int(count) >= settings.RATE_LIMIT_REQUESTS_PER_HOUR:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        pipe = r.pipeline()
        pipe.incr(key, 1)
        pipe.expire(key, 3600)
        pipe.execute()
    except HTTPException:
        raise
    except Exception:
        # Keep local development and CI usable if Redis is not available.
        return
