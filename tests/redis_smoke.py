from uuid import uuid4

from chef_memory import MAX_TURNS, load_memory, remember
from shared_cache import allow_ai_request, redis_client

key = uuid4().hex
record = {"terms": ["photo"], "sources": [{"path": "README.md", "line": 8}]}
assert redis_client() is not None
for _ in range(MAX_TURNS + 2):
    remember(key, record)
assert load_memory(key) == [record] * MAX_TURNS
assert redis_client().ttl(f"recipe:chef:{key}") > 0
assert all(allow_ai_request(key) for _ in range(12))
assert not allow_ai_request(key)
print("Redis shared context, bounded history, expiry, and AI rate limit verified.")
