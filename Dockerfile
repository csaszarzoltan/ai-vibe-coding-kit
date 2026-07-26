# Dockerfile — AI Vibe Coding Kit
# See shared/patterns/railway-deploy-config.md for details

FROM python:3.11-slim

WORKDIR /app

# Install uv for fast deps
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy app
COPY . .

# Non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["sh", "-c", "uvicorn ai_vibe_coding.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
