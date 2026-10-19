#!/usr/bin/env python3
"""Deploy the ML inference service to a Hugging Face Space (Docker SDK).

The Space gets the full ml-service source plus the prebuilt research corpus,
BM25 index, and FAISS index, so first boot only downloads the transformer
models (sentence-transformers + NLI cross-encoder) from the HF hub.

Usage:
    HF_TOKEN=hf_xxx MODEL_SERVICE_KEY=xxx python3 scripts/deploy_hf_space.py

Environment:
    HF_TOKEN             Hugging Face token with write access (required)
    HF_USERNAME          HF username (default: Himanshu90909)
    SPACE_NAME           Space repo name (default: evidence-verification-ml)
    MODEL_SERVICE_KEY    shared secret between Vercel and the ML service
                         (required; generated if unset and printed once)
"""
import os
import secrets
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ml-service/

SKIP = {
    "__pycache__", "tests", "models", ".pytest_cache", ".ruff_cache",
    "Dockerfile",  # replaced by the HF Space variant below
}

SPACE_DOCKERFILE = """\
# HF Spaces variant of the ML inference Dockerfile.
# Differences vs the standalone Dockerfile: no VOLUME (Spaces are ephemeral),
# writable HF cache inside the container, prebuilt corpus/indexes shipped in
# the repo, PREBUILD_INDEX=0 so boot never rebuilds indexes.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PIP_NO_CACHE_DIR=1 \\
    HF_HOME=/app/hf_cache \\
    PREBUILD_INDEX=0

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \\
    libgomp1 libopenblas0 curl \\
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY data/ ./data/

RUN useradd -m -u 1000 mluser && chown -R mluser /app
USER mluser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=600s --retries=5 \\
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""


def build_bundle() -> str:
    """Assemble the Space repo contents from ml-service/ into a temp dir."""
    tmp = tempfile.mkdtemp(prefix="hf-space-")
    for name in os.listdir(ROOT):
        src = os.path.join(ROOT, name)
        if name in SKIP or name.startswith("."):
            continue
        dst = os.path.join(tmp, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        else:
            shutil.copy2(src, dst)
    with open(os.path.join(tmp, "Dockerfile"), "w") as f:
        f.write(SPACE_DOCKERFILE)
    return tmp


def main() -> int:
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        print("HF_TOKEN is required (write-access token from https://huggingface.co/settings/tokens)",
              file=sys.stderr)
        return 1
    username = os.environ.get("HF_USERNAME", "Himanshu90909")
    space_name = os.environ.get("SPACE_NAME", "evidence-verification-ml")
    key = os.environ.get("MODEL_SERVICE_KEY") or secrets.token_urlsafe(32)
    key_from_env = bool(os.environ.get("MODEL_SERVICE_KEY"))

    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("pip install huggingface_hub first", file=sys.stderr)
        return 1

    api = HfApi(token=hf_token)
    repo_id = f"{username}/{space_name}"

    print(f"Creating/ensuring Space {repo_id} ...")
    api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="docker", private=True, exist_ok=True)

    readme = f"""---
title: Evidence Verification ML Service
emoji: "\U0001f50e"
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 8000
pinned: false
---

FastAPI ML inference service for the Evidence-Based Claim Verification platform.
Dockerized hybrid retrieval (BM25 + FAISS dense) + NLI claim verification.
"""
    tmp = build_bundle()
    try:
        with open(os.path.join(tmp, "README.md"), "w") as f:
            f.write(readme)
        print("Uploading Space files (code + corpus + indexes, ~130 MB) ...")
        api.upload_folder(repo_id=repo_id, repo_type="space", folder_path=tmp,
                          commit_message="Deploy ML inference service (prebuilt indexes)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # Shared secret between Vercel and this service.
    api.add_space_secret(repo_id=repo_id, key="ML_API_KEY", value=key)

    url = f"https://{username}-{space_name}.hf.space"
    print(f"\nSpace: https://huggingface.co/spaces/{repo_id}")
    print(f"Public API: {url}")
    print("\nSet these in Vercel (Production + Preview):")
    print(f"  ML_API_URL={url}")
    if not key_from_env:
        print(f"  MODEL_SERVICE_KEY={key}   <- generated now, save it")
    else:
        print("  MODEL_SERVICE_KEY=<the value you passed in>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
