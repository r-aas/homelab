FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir \
    fastapi>=0.115.0 \
    "uvicorn[standard]>=0.32.0" \
    pydantic>=2.10.0 \
    pydantic-settings>=2.6.0 \
    httpx>=0.28.0 \
    ollama>=0.4.0 \
    traceloop-sdk>=0.34.0 \
    opentelemetry-instrumentation-httpx>=0.48b0

# Copy source
COPY src/ ./src/

# Create data directory
RUN mkdir -p /data/agents

WORKDIR /app/src

EXPOSE 8080

CMD ["python", "main.py"]
