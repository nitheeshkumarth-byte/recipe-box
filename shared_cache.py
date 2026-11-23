import hashlib
import os
from functools import lru_cache
from flask import current_app, has_app_context


class CacheUnavailable(RuntimeError):
    pass


def redis_client():
    if has_app_context() and current_app.config.get("LOCAL_DEVELOPMENT"):
        return None
    url = os.getenv("REDIS_URL")
    return connect_redis(url) if url else None


@lru_cache(maxsize=1)
def connect_redis(url):
    from redis import Redis
    return Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2, decode_responses=True)


def allow_ai_request(user_id):
    client = redis_client()
    if client is None:
        return True
    from redis.exceptions import RedisError
    identifier = hashlib.sha256(user_id.encode()).hexdigest()
    try:
        count = client.eval("""
            local count = redis.call('INCR', KEYS[1])
            if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
            return count
        """, 1, f"recipe:ai:{identifier}", 60)
    except RedisError as error:
        raise CacheUnavailable("Shared rate limiting is temporarily unavailable.") from error
    return count <= 12
