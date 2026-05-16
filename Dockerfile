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

# Copy application source
COPY src/ ./src/
COPY data/ ./data/

# Non-root user for security (Hugging Face Spaces requires UID 1000)
RUN useradd -m -u 1000 user
USER user

# Hugging Face Spaces port
EXPOSE 7860

# Health check — hits the FastAPI health endpoint (not MCP)
# The REST API (main.py) is a separate process; MCP server exposes its own health
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')" || exit 1

# Environment defaults
ENV TRUEARCH_DATA_DIR=data/frameworks \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    HOST=0.0.0.0

# Run the MCP server in streamable-HTTP mode
CMD ["python", "-m", "src.mcp.server", "--http"]
