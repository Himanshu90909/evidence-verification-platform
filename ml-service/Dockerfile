# ---------------------------------------------------------------------------
# Evidence Verification Platform - ML inference service
# Independently deployable Python service (FastAPI + PyTorch + Transformers).
# Build:  docker build -t evp-ml-service ./ml-service
# Run:    docker run -p 8000:8000 -v evp_data:/data -e ML_API_KEY=... evp-ml-service
# ---------------------------------------------------------------------------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/data/hf_cache

WORKDIR /app

# System deps for faiss / torch (OpenBLAS, OpenMP)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 libopenblas0 curl \
    && apt-get clean

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY scripts/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Persistable volume: corpus + indexes + HF model cache
RUN mkdir -p /data
VOLUME /data

# Non-root user
RUN useradd -m -u 1000 mluser && chown -R mluser /app /data
USER mluser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# On first boot the entrypoint builds corpus/indexes if the volume is empty
# (needs network access to HuggingFace). Set PREBUILD_INDEX=0 to skip.
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
