"""Check the optional search index with synthetic embeddings, without calling Gemini."""

import os
from unittest.mock import patch
from urllib.parse import urlsplit

from flask import g
from flask_migrate import upgrade

database = os.environ["RECIPE_TEST_POSTGRES_URL"]
target = urlsplit(database)
assert target.hostname in {"127.0.0.1", "localhost"} and target.path == "/recipe_box_ci"
os.environ.update(DATABASE_URL=database, CHEF_HYBRID_SEARCH="1", CHEF_RAG_PROVIDER="gemini",
                  GEMINI_API_KEY="ci-placeholder-never-sent")

from app import app
from chef_rag import index
from chef_vectors import digest, similar_passages

guide = next(passage for passage in index()[0] if passage.path == "docs/chef_help.md" and "5 MB" in passage.text)
vector = "[" + ",".join(["1"] + ["0"] * 767) + "]"

with app.app_context():
    upgrade()
with patch("chef_rag.index", return_value=([guide], {})):
    with patch("chef_vectors.embed", return_value=[vector]):
        result = app.test_cli_runner().invoke(args=["rebuild-chef-index"])
        assert result.exit_code == 0, result.exception

with app.test_request_context():
    g.recipe_user_id = "3fcfe498-5ad4-45ad-88c3-bd92c224fa71"
    with patch("chef_vectors.embed", return_value=[vector]):
        hits = similar_passages("What is the photo upload limit?")
        assert hits[(guide.path, guide.line, digest(guide))] > .99

print("pgvector bootstrap, screened source fingerprints, and runtime-role similarity reads passed.")
