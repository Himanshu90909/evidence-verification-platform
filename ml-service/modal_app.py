"""Modal deployment for the ML inference service.

Serves the exact same FastAPI application (hybrid BM25+dense retrieval, NLI
cross-encoder, uncertainty estimation) via `@modal.asgi_app`, so production
predictions and research experiments run identical code.

IMPORTANT: Modal re-executes this module inside the container when hydrating
functions, and the object graph built there must match the one built at deploy
time. Therefore every statement in this file must be deterministic: no
file-existence guards, no os.environ reads at module level. The requirements
list is a static constant kept in sync with requirements.txt, and the API key
comes from the named Modal secret "ml-service-key".

Deployment (free Starter plan, $30/mo credits — roughly $0.0003 per verification):

    pip install modal
    export MODAL_TOKEN_ID=... MODAL_TOKEN_SECRET=...   # modal.com Settings → API tokens
    modal secret create ml-service-key ML_API_KEY=<shared secret>
    modal deploy modal_app.py
"""
import os

import modal

ROOT = os.path.dirname(os.path.abspath(__file__))

# Keep in sync with requirements.txt (torch installed separately, CPU wheel index;
# pytest excluded from the production image).
_REQUIREMENTS = [
    "datasets>=2.20",
    "faiss-cpu>=1.8.0",
    "fastapi==0.115.6",
    "httpx>=0.27",
    "numpy>=1.26",
    "pandas>=2.0",
    "pydantic-settings==2.7.1",
    "pydantic==2.10.5",
    "rank-bm25==0.2.2",
    "scikit-learn>=1.5",
    "sentence-transformers>=3.1",
    "transformers>=4.44,<5",
    "uvicorn[standard]==0.34.0",
]

base_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgomp1", "libopenblas0", "curl")
    .pip_install("torch>=2.2,<3", index_url="https://download.pytorch.org/whl/cpu")
    .pip_install(*_REQUIREMENTS)
    .env({"PREBUILD_INDEX": "0", "HF_HOME": "/root/.cache/huggingface"})
)

app = modal.App("evidence-verification-ml")

# Import AFTER app creation; kept in its own module so only that file's source
# is needed for this build step.
from prewarm import prewarm  # noqa: E402

image = (
    base_image.run_function(prewarm)
    .add_local_dir(os.path.join(ROOT, "app"), "/app/app")
    .add_local_dir(os.path.join(ROOT, "data"), "/app/data")
    .add_local_file(os.path.join(ROOT, "main.py"), "/app/main.py")
    .add_local_file(
        os.path.join(ROOT, "scripts", "docker-entrypoint.sh"), "/app/entrypoint.sh"
    )
)

# Named secret (create once: `modal secret create ml-service-key ML_API_KEY=...`).
_secret = modal.Secret.from_name("ml-service-key", required_keys=["ML_API_KEY"])


@app.function(
    image=image,
    secrets=[_secret],
    scaledown_window=300,  # stay warm 5 min after the last request
    timeout=120,
)
@modal.asgi_app()
def api():
    import os
    import sys

    os.chdir("/app")  # service resolves ./data relative to CWD (Docker used WORKDIR /app)
    sys.path.insert(0, "/app")
    import main

    return main.app
