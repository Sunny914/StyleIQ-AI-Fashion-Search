# ProductIQ production API image (Phase 15A).
# Build: docker build -t productiq-api:local .
# Run:   docker run --rm -p 8000:8000 -e APP_ENV=production productiq-api:local

FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Runtime libs for wheels (LightGBM OpenMP). No DB or model downloads at build time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 productiq \
    && useradd --uid 1000 --gid productiq --home-dir /app --no-log-init productiq

COPY pyproject.toml README.md ./
COPY src ./src

# Install CPU PyTorch before the project so sentence-transformers does not pull CUDA wheels.
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch>=2.0" \
    && pip install --no-cache-dir .

RUN chown -R productiq:productiq /app

USER productiq

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"

CMD ["uvicorn", "productiq.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
