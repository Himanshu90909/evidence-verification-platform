#!/usr/bin/env python3
"""Deploy the ML inference service to Modal.

Prereqs:
    pip install modal
    export MODAL_TOKEN_ID=...   (from modal.com -> Settings -> API tokens)
    export MODAL_TOKEN_SECRET=...
    export MODEL_SERVICE_KEY=<shared secret with the Vercel web app>

Run:
    python3 scripts/deploy_modal.py

Prints the public HTTPS URL of the ML service when done.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    missing = [
        v for v in ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "MODEL_SERVICE_KEY")
        if not os.environ.get(v)
    ]
    if missing:
        print(f"Missing env vars: {', '.join(missing)}", file=sys.stderr)
        return 1

    try:
        import modal  # noqa: F401
    except ImportError:
        print("pip install modal first", file=sys.stderr)
        return 1

    print("Deploying to Modal (image build incl. models: first run takes a few minutes) ...")
    proc = subprocess.run(
        ["modal", "deploy", os.path.join(ROOT, "modal_app.py")],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    print(out.strip()[-1500:])
    if proc.returncode != 0:
        return proc.returncode

    # Extract the web URL from the deploy output.
    url = None
    for token in out.replace("(", " ").replace(")", " ").split():
        if token.startswith("https://") and "modal" in token:
            url = token.rstrip(".,;")
    if url:
        print(f"\nML service deployed. API base URL: {url}")
        print("Set in Vercel (Production + Preview):")
        print(f"  ML_API_URL={url}")
        print("  MODEL_SERVICE_KEY=<the value you passed>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
