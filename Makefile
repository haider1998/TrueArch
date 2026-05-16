.PHONY: help install test lint serve-mcp serve-api status

APP_NAME ?= truearch-mcp
PORT     ?= 7860

help:
	@echo ""
	@echo "TrueArch — Development Commands"
	@echo "────────────────────────────────────────────"
	@echo "  make install      Install dependencies"
	@echo "  make test         Run full test suite"
	@echo "  make serve-mcp    Start MCP server (HTTP mode, local)"
	@echo "  make serve-api    Start REST API (FastAPI)"
	@echo "  make status       Check local server health"
	@echo ""

install:
	pip install --upgrade pip
	pip install -r requirements.txt

test:
	python -m pytest tests/ -v

test-fast:
	python -m pytest tests/ -q

serve-mcp:
	@echo "Starting TrueArch MCP server (HTTP) on port $(PORT)..."
	PORT=$(PORT) python -m src.mcp.server --http

serve-mcp-stdio:
	@echo "Starting TrueArch MCP server (stdio mode — for IDE integration)..."
	python -m src.mcp.server

serve-api:
	@echo "Starting TrueArch REST API on port 8000..."
	uvicorn src.api.main:app --reload --port 8000

status:
	@echo "Checking http://127.0.0.1:$(PORT)/health ..."
	@curl -sf http://127.0.0.1:$(PORT)/health | python3 -m json.tool || echo "Server not responding"
