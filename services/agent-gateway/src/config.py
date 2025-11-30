"""Configuration for Agent Gateway."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Agent Gateway settings."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    # MCP Registry integration
    mcp_registry_url: str = "http://registry:8080"

    # Ollama
    ollama_host: str = "http://host.docker.internal:11434"
    default_model: str = "qwen3:30b"
    coder_model: str = "qwen2.5-coder:32b"

    # Agent discovery
    agent_discovery_interval: int = 60  # seconds
    health_check_timeout: int = 10  # seconds

    # Storage
    data_dir: str = "/data"

    # Observability (OpenLLMetry)
    otlp_endpoint: str = "http://jaeger:4318"  # OTLP HTTP endpoint
    tracing_enabled: bool = True
    service_name: str = "agent-gateway"

    # Auth
    auth_enabled: bool = True
    auth_server_url: str = "http://auth-server:8888"
    public_paths: str = "/health,/.well-known/agent.json,/docs,/openapi.json"

    model_config = {"env_prefix": "AGENT_GATEWAY_"}


settings = Settings()
