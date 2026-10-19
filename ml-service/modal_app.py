"""Modal deployment for the ML inference service.

Serves the exact same FastAPI application (hybrid BM25+dense retrieval, NLI
cross-encoder, uncertainty estimation) via `@modal.asgi_app`, so production
predictions and research experiments run identical code.

Deployment (free Starter plan, $30/mo credits — this service costs roughly
$0.0003 per verification):

    pip install modal
    export MODAL_TOKEN_ID=... MODAL_TOKEN_SECRET=...   # from modal.com Settings → API tokens
    export MODEL_SERVICE_KEY=<shared secret>
    python3 scripts/deploy_modal.py

The image bakes in the corpus, BM25 index, FAISS index, and both transformer
models, so a cold-started container serves its first request ~20-30s after
waking. The app scales to zero when idle.
"""
import os

import modal

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Image: CPU-only torch + requirements + code + prebuilt corpus/indexes,
# then bake the transformer model downloads into the image via a build step.
# ---------------------------------------------------------------------------
requirements = [
    line.strip()
    for line in open(os.path.join(ROOT, "requirements.txt"))
    if line.strip() and not line.startswith("#")
]
# torch is installed separately from the CPU-only wheel index (much smaller image).
_rest = [
    r for r in requirements
    if not r.lower().startswith("torch") and not r.startswith("pytest")
]

base_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgomp1", "libopenblas0", "curl")
    .pip_install("torch>=2.2,<3", index_url="https://download.pytorch.org/whl/cpu")
    .pip_install(*_rest)
    .env({"PREBUILD_INDEX": "0", "HF_HOME": "/root/.cache/huggingface"})
    .add_local_dir(os.path.join(ROOT, "app"), "/app/app")
    .add_local_dir(os.path.join(ROOT, "data"), "/app/data")
    .add_local_file(os.path.join(ROOT, "main.py"), "/app/main.py")
    .add_local_file(os.path.join(ROOT, "scripts", "docker-entrypoint.sh"), "/app/entrypoint.sh")
)

app = modal.App("evidence-verification-ml")


def prewarm() -> str:
    """Runs inside the image build: loads corpus, indexes, and models so their
    downloads are baked into the deployed image (fast, reliable cold starts)."""
    import sys

    sys.path.insert(0, "/app")
    import main  # noqa: F401  (import triggers nothing; we call the loader)

    main._load_backends()
    assert main.service_state["status"] == "ok", main.service_state
    return "ok"


image = base_image.run_function(prewarm)

# ---------------------------------------------------------------------------
# Web endpoint: the exact same FastAPI app used everywhere else.
# ---------------------------------------------------------------------------
KEY = os.environ.get("MODEL_SERVICE_KEY", "")
if not KEY:
    raise SystemExit(
        "MODEL_SERVICE_KEY env var required (shared secret with the web app)."
    )


@app.function(
    image=image,
    secrets=[modal.Secret.from_dict({"ML_API_KEY": KEY})],
    scaledown_window=300,  # stay warm 5 min after the last request
    timeout=120,
)
@modal.asgi_app()
def api():
    import sys

    sys.path.insert(0, "/app")
    import main

    return main.app
