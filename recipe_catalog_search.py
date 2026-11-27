"""Hybrid retrieval over ingredient names in an already authorized recipe catalog."""

from collections import defaultdict
from contextlib import closing
from functools import lru_cache
from hashlib import sha256
import os
from pathlib import Path
import re
import sqlite3
from threading import Lock
from urllib.parse import urlsplit


_index_lock = Lock()
MAX_COSINE_DISTANCE = 0.65


@lru_cache(maxsize=1)
def _chroma(path, server, model_path):
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

    settings = Settings(anonymized_telemetry=False)
    embedding = ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])
    if model_path:
        embedding.DOWNLOAD_PATH = Path(model_path)
    if server:
        url = urlsplit(server)
        client = chromadb.HttpClient(
            host=url.hostname, port=url.port or (443 if url.scheme == "https" else 80),
            ssl=url.scheme == "https", settings=settings,
        )
    else:
        client = chromadb.PersistentClient(path=str(path), settings=settings)
    return client, embedding


def _keyword_matches(query, ingredients):
    terms = dict.fromkeys(re.findall(r"[^\W_]+", query, flags=re.UNICODE))
    if not terms:
        return []
    expression = " OR ".join(f'"{term}"' for term in terms)
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.execute("CREATE VIRTUAL TABLE catalog USING fts5(recipe_id UNINDEXED, ingredients)")
        connection.executemany("INSERT INTO catalog VALUES (?, ?)", ingredients.items())
        return [row[0] for row in connection.execute(
            "SELECT recipe_id FROM catalog WHERE catalog MATCH ? ORDER BY rank, recipe_id", (expression,)
        )]


def _vector_matches(query, ingredients, eligible, path, scope):
    with _index_lock:
        client, embedding = _chroma(path, os.getenv("RECIPE_CHROMA_URL"), os.getenv("RECIPE_MINILM_PATH"))
        # Each owner has a distinct collection. Store vectors and text digests only.
        scope_id = sha256(scope.encode()).hexdigest()[:32]
        collection = client.get_or_create_collection(
            name=f"recipe-ingredients-{scope_id}", embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
        )
        existing = collection.get(include=["metadatas"])
        previous = {key: meta["digest"] for key, meta in zip(existing["ids"], existing["metadatas"])}
        digests = {key: sha256(value.encode()).hexdigest() for key, value in ingredients.items()}
        changed = [key for key, digest in digests.items() if previous.get(key) != digest]
        removed = sorted(previous.keys() - ingredients.keys())
        for start in range(0, len(removed), 64):
            collection.delete(ids=removed[start:start + 64])
        for start in range(0, len(changed), 64):
            keys = changed[start:start + 64]
            collection.upsert(
                ids=keys, embeddings=embedding([ingredients[key] for key in keys]),
                metadatas=[{"digest": digests[key]} for key in keys],
            )
        if not eligible:
            return []
        matches = collection.query(
            query_embeddings=embedding([query]), ids=list(eligible),
            include=["distances"], n_results=min(40, len(eligible)),
        )
        return [
            key for key, distance in zip(matches["ids"][0], matches["distances"][0])
            if distance <= MAX_COSINE_DISTANCE
        ]


def ranked_ingredients(query, ingredients, eligible, *, path, scope, logger):
    candidates = {key: text for key, text in ingredients.items() if key in eligible}
    try:
        keywords = _keyword_matches(query, candidates)
    except sqlite3.OperationalError:
        logger.warning("Recipe BM25 is unavailable")
        keywords = []
    try:
        vectors = _vector_matches(query, ingredients, candidates, path, scope)
    except Exception as error:
        # Chroma is optional and must never take the existing collection search offline.
        logger.warning("Recipe vector search unavailable (%s)", type(error).__name__)
        vectors = []
    ranks = defaultdict(float)
    for matches in (keywords, vectors):
        for position, key in enumerate(matches, start=1):
            ranks[key] += 1 / (60 + position)
    return sorted(ranks, key=lambda key: (-ranks[key], -int(key)))
