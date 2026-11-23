"""Opt-in pgvector reranking using only screened project passages."""

import hashlib
import math
import os

import click
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from model import db


def enabled():
    return (os.getenv("CHEF_HYBRID_SEARCH") == "1"
            and os.getenv("CHEF_RAG_PROVIDER") == "gemini"
            and bool(os.getenv("GEMINI_API_KEY")))


def digest(passage):
    return hashlib.sha256(passage.text.encode()).hexdigest()


def model():
    return os.getenv("CHEF_EMBEDDING_MODEL", "gemini-embedding-001")


def embed(contents, task):
    from google import genai
    from google.genai import types
    with genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options=types.HttpOptions(timeout=8000)) as client:
        response = client.models.embed_content(
            model=model(), contents=contents,
            config=types.EmbedContentConfig(task_type=task, output_dimensionality=768),
        )
    vectors = []
    for embedding in response.embeddings or []:
        values = embedding.values or []
        if len(values) != 768 or not all(math.isfinite(value) for value in values):
            raise ValueError("Unexpected embedding dimension or value.")
        vectors.append("[" + ",".join(map(str, values)) + "]")
    if len(vectors) != len(contents):
        raise ValueError("Unexpected number of embeddings.")
    return vectors


def similar_passages(question):
    if not enabled() or db.engine.dialect.name != "postgresql":
        return {}
    from google.genai import errors
    try:
        result = db.session.execute(text("""
            SELECT path, line, digest,
                1 - (embedding OPERATOR(extensions.<=>) CAST(:vector AS extensions.vector)) AS similarity
            FROM recipe_box_vectors.passages
            WHERE model = :model
            ORDER BY embedding OPERATOR(extensions.<=>) CAST(:vector AS extensions.vector)
            LIMIT 10
        """), {"vector": embed([question], "RETRIEVAL_QUERY")[0], "model": model()})
        return {(row.path, row.line, row.digest): row.similarity for row in result if row.similarity >= .55}
    except (SQLAlchemyError, errors.APIError, ValueError, OSError):
        return {}
    finally:
        db.session.rollback()


def register_vector_commands(app):
    @app.cli.command("rebuild-chef-index")
    def rebuild_index():
        """Rebuild the optional vector index from the current release."""
        from chef_rag import index
        if not enabled() or db.engine.dialect.name != "postgresql":
            raise click.ClickException("Enable Gemini hybrid search and use PostgreSQL before rebuilding.")
        passages, _ = index()
        rows = []
        for offset in range(0, len(passages), 12):
            batch = passages[offset:offset + 12]
            for passage, vector in zip(batch, embed([p.text for p in batch], "RETRIEVAL_DOCUMENT"), strict=True):
                rows.append({"path": passage.path, "line": passage.line, "digest": digest(passage),
                             "vector": vector, "model": model()})
        with db.engine.begin() as connection:
            for statement in (
                "CREATE SCHEMA IF NOT EXISTS extensions",
                "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions",
                "CREATE SCHEMA IF NOT EXISTS recipe_box_vectors",
                """CREATE TABLE IF NOT EXISTS recipe_box_vectors.passages (
                    path text NOT NULL, line integer NOT NULL, digest text NOT NULL, model text NOT NULL,
                    embedding extensions.vector(768) NOT NULL, PRIMARY KEY (path, line))""",
                "GRANT USAGE ON SCHEMA extensions, recipe_box_vectors TO recipe_box_runtime",
                "GRANT SELECT ON recipe_box_vectors.passages TO recipe_box_runtime",
                "DELETE FROM recipe_box_vectors.passages",
            ):
                connection.execute(text(statement))
            if rows:
                connection.execute(text("""
                    INSERT INTO recipe_box_vectors.passages (path, line, digest, embedding, model)
                    VALUES (:path, :line, :digest, CAST(:vector AS extensions.vector), :model)
                """), rows)
        click.echo(f"Indexed {len(rows)} vetted project passages.")
