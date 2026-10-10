# ==============================================================================
# Stage 1: Build the React Studio Web UI
# ==============================================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /build/vero-studio

COPY vero-studio/package*.json ./
RUN npm ci

COPY vero-studio/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Production Python Runtime
# ==============================================================================
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy backend source and compiled frontend static assets
COPY vero-cli/ /app/vero-cli/
COPY --from=frontend-builder /build/vero-cli/vero/static/ /app/vero-cli/vero/static/

# Install Python package and dependencies
RUN cd /app/vero-cli && uv pip install -e . --system

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

# Start Vero Studio server
CMD ["vero", "serve", "--host", "0.0.0.0", "--port", "8000"]
