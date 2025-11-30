"""Ollama integration for local model support."""

import logging
from typing import Any, AsyncIterator, Optional

import httpx
from ollama import AsyncClient

from config import settings
from models import LocalModelConfig

logger = logging.getLogger(__name__)


class OllamaService:
    """Service for interacting with local Ollama models."""

    def __init__(self):
        """Initialize Ollama client."""
        self.client = AsyncClient(host=settings.ollama_host)
        self._available_models: dict[str, LocalModelConfig] = {}
        self._model_capabilities = {
            "qwen3": ["reasoning", "chat", "tools", "coding"],
            "qwen2.5-coder": ["coding", "tools", "chat"],
            "dolphin-mixtral": ["chat", "uncensored", "reasoning"],
            "llama3": ["chat", "reasoning", "tools"],
            "mistral": ["chat", "reasoning", "coding"],
            "codellama": ["coding"],
            "deepseek-coder": ["coding", "tools"],
        }

    async def discover_models(self) -> list[LocalModelConfig]:
        """Discover available Ollama models."""
        try:
            response = await self.client.list()
            models = []

            # Handle both dict and ListResponse object formats
            model_list = response.get("models", []) if isinstance(response, dict) else getattr(response, "models", [])

            for model in model_list:
                # Handle both dict and Model object formats
                if isinstance(model, dict):
                    name = model.get("name", "")
                    details = model.get("details", {})
                else:
                    name = getattr(model, "name", "") or getattr(model, "model", "")
                    details = getattr(model, "details", {}) or {}
                    if not isinstance(details, dict):
                        details = {"family": getattr(details, "family", "")}

                if not name:
                    continue

                model_id = name.split(":")[0] if ":" in name else name

                # Determine capabilities based on model family
                capabilities = []
                for family, caps in self._model_capabilities.items():
                    if family in model_id.lower():
                        capabilities = caps
                        break

                if not capabilities:
                    capabilities = ["chat"]  # Default

                config = LocalModelConfig(
                    name=name,
                    model_id=name,
                    description=f"Local Ollama model: {name}",
                    capabilities=capabilities,
                    context_length=details.get("context_length", 8192) if isinstance(details, dict) else 8192,
                    is_default=(name == settings.default_model),
                )
                models.append(config)
                self._available_models[name] = config

            logger.info(f"Discovered {len(models)} Ollama models")
            return models

        except Exception as e:
            logger.error(f"Failed to discover Ollama models: {e}")
            return []

    async def is_available(self) -> bool:
        """Check if Ollama is available."""
        try:
            await self.client.list()
            return True
        except Exception:
            return False

    async def get_model(self, model_name: str) -> Optional[LocalModelConfig]:
        """Get model config by name."""
        if not self._available_models:
            await self.discover_models()
        return self._available_models.get(model_name)

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        tools: Optional[list[dict[str, Any]]] = None,
        stream: bool = False,
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        """Send chat completion request to Ollama."""
        try:
            if stream:
                return self._stream_chat(model, messages, tools)

            response = await self.client.chat(
                model=model,
                messages=messages,
                tools=tools,
                options={"num_ctx": 8192},
            )
            return response

        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            raise

    async def _stream_chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream chat completion."""
        async for chunk in await self.client.chat(
            model=model,
            messages=messages,
            tools=tools,
            stream=True,
            options={"num_ctx": 8192},
        ):
            yield chunk

    async def generate_embeddings(self, text: str, model: str = "nomic-embed-text") -> list[float]:
        """Generate embeddings for text."""
        try:
            response = await self.client.embeddings(model=model, prompt=text)
            return response.get("embedding", [])
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return []


# Global instance
ollama_service = OllamaService()
