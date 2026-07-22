# ── Stage 1: Build ────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps for building packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies into a prefix we can copy to the runtime stage
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Non-root user for security (Hugging Face Spaces requires UID 1000).
# Created BEFORE the COPYs so --chown can hand ownership over directly:
# the server writes data/telemetry.db at runtime, which a root-owned
# directory would make impossible (sqlite3 "unable to open database file").
RUN useradd -m -u 1000 user

# Copy application source, owned by the runtime user
COPY --chown=user:user src/ ./src/
COPY --chown=user:user data/ ./data/

# /app itself must be writable for WAL sidecar files (-wal, -shm)
RUN chown user:user /app

USER user

# Hugging Face Spaces port
EXPOSE 7860

# Health check — hits the FastAPI health endpoint (not MCP)
# The REST API (main.py) is a separate process; MCP server exposes its own health
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')" || exit 1

# Environment defaults
#   TRUEARCH_ALLOWED_HOSTS=* — this is a public, read-only, unauthenticated
#   server, so it must accept the deployment's own hostname (e.g. *.hf.space).
#   The SDK's localhost-only default would 421 every remote MCP client while
#   /health still returned 200, making the Space look silently broken.
ENV TRUEARCH_DATA_DIR=/app/data/frameworks \
    TRUEARCH_DB_PATH=/app/data/telemetry.db \
    TRUEARCH_ALLOWED_HOSTS=* \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    HOST=0.0.0.0

# Run the MCP server in streamable-HTTP mode
CMD ["python", "-m", "src.mcp.server", "--http"]
