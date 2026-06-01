# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — Builder: install deps into a clean layer
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps needed to compile some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt requirements-prod.txt ./
RUN pip install --upgrade pip \
 && pip install --prefix=/install --no-cache-dir -r requirements-prod.txt

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — Runtime: lean final image
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source
COPY src/ ./src/
COPY requirements-prod.txt ./

# Create directories for runtime data
RUN mkdir -p /app/local_qdrant_storage /app/mlruns /app/data \
 && chown -R appuser:appuser /app

USER appuser

# FastEmbed model cache location
ENV FASTEMBED_CACHE_DIR=/app/.cache/fastembed
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose FastAPI port
EXPOSE 8000

# Health check — Docker will mark container unhealthy if this fails
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Start the FastAPI server
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--log-level", "info"]
