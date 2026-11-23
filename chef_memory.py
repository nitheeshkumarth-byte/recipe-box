import hashlib
import json
import time

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError

from model import ChefSessionCache, db
from shared_cache import CacheUnavailable, redis_client

MAX_TURNS = 8
TTL_SECONDS = 30 * 60


def cache_key(session_token):
    return hashlib.sha256(f"chef-chat:{session_token}".encode()).hexdigest()


def load_memory(key):
    client = redis_client()
    if client is not None:
        from redis.exceptions import RedisError
        try:
            return [json.loads(value) for value in client.lrange(f"recipe:chef:{key}", 0, -1)]
        except (RedisError, ValueError) as error:
            raise CacheUnavailable("Chef session cache is unavailable.") from error
    table = ChefSessionCache.__table__
    value = db.session.execute(
        select(table.c.value).where(
            table.c.session_key == key, table.c.expires_at > int(time.time())
        )
    ).scalar_one_or_none()
    # The model call must not keep a database connection checked out.
    db.session.rollback()
    return value or []


def remember(key, turn):
    client = redis_client()
    if client is not None:
        from redis.exceptions import RedisError
        redis_key = f"recipe:chef:{key}"
        try:
            with client.pipeline(transaction=True) as pipeline:
                pipeline.rpush(redis_key, json.dumps(turn))
                pipeline.ltrim(redis_key, -MAX_TURNS, -1)
                pipeline.expire(redis_key, TTL_SECONDS)
                pipeline.execute()
        except RedisError as error:
            raise CacheUnavailable("Chef session cache is unavailable.") from error
        return
    table = ChefSessionCache.__table__
    insert = postgres_insert if db.engine.dialect.name == "postgresql" else sqlite_insert
    for _ in range(3):
        now = int(time.time())
        existing = db.session.execute(
            select(table.c.version, table.c.value, table.c.expires_at)
            .where(table.c.session_key == key)
        ).one_or_none()
        if existing is None:
            statement = (
                insert(table).values(session_key=key, version=1, value=[turn], expires_at=now + TTL_SECONDS)
                .on_conflict_do_nothing(index_elements=[table.c.session_key])
            )
        else:
            history = existing.value if existing.expires_at > now else []
            statement = (
                update(table)
                .where(table.c.session_key == key, table.c.version == existing.version)
                .values(version=existing.version + 1, value=[*history, turn][-MAX_TURNS:],
                        expires_at=now + TTL_SECONDS)
            )
        if db.session.execute(statement).rowcount == 1:
            db.session.execute(delete(table).where(table.c.expires_at <= now))
            db.session.commit()
            return
        db.session.rollback()
    raise SQLAlchemyError("Concurrent chef memory updates did not settle")
