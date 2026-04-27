# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHERUSAGESTATS=false

WORKDIR /app

# System deps: only what psycopg-binary needs, plus a tini-style init.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ca-certificates \
        tini \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY dashboard ./dashboard
COPY data ./data
COPY scripts ./scripts

RUN pip install --upgrade pip \
 && pip install -e ".[dashboard]"

# Azure App Service for Linux maps PORT via WEBSITES_PORT or 80; we honour
# both via the startup script.
EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash", "-lc", "streamlit run dashboard/streamlit_app.py \
        --server.port ${PORT:-8000} \
        --server.address 0.0.0.0 \
        --server.headless true \
        --browser.gatherUsageStats false"]
