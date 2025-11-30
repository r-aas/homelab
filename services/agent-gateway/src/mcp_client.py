"""Client for integrating with the MCP Registry."""

import logging
from typing import Any, Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


class MCPRegistryClient:
    """Client for the MCP Registry service."""

    def __init__(self):
        """Initialize MCP Registry client."""
        self.base_url = settings.mcp_registry_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> bool:
        """Check if MCP Registry is healthy."""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"MCP Registry health check failed: {e}")
            return False

    async def list_servers(self) -> list[dict[str, Any]]:
        """List all MCP servers from registry."""
        try:
            client = await self._get_client()
            response = await client.get("/api/servers")
            response.raise_for_status()
            data = response.json()
            return data.get("servers", [])
        except Exception as e:
            logger.error(f"Failed to list MCP servers: {e}")
            return []

    async def get_server(self, path: str) -> Optional[dict[str, Any]]:
        """Get a specific MCP server by path."""
        try:
            client = await self._get_client()
            response = await client.get(f"/api/servers/{path.lstrip('/')}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get MCP server {path}: {e}")
            return None

    async def list_agents(self) -> list[dict[str, Any]]:
        """List all A2A agents from registry."""
        try:
            client = await self._get_client()
            response = await client.get("/api/agents")
            response.raise_for_status()
            data = response.json()
            return data.get("agents", [])
        except Exception as e:
            logger.error(f"Failed to list agents from MCP registry: {e}")
            return []

    async def register_agent(self, agent_data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Register an agent with the MCP Registry."""
        try:
            client = await self._get_client()
            response = await client.post("/api/agents/register", json=agent_data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to register agent: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to register agent: {e}")
            return None

    async def search(
        self,
        query: str,
        entity_types: Optional[list[str]] = None,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for servers and agents using semantic search."""
        try:
            client = await self._get_client()
            params = {
                "query": query,
                "max_results": max_results,
            }
            if entity_types:
                params["entity_types"] = ",".join(entity_types)

            response = await client.get("/api/search", params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    async def get_server_tools(self, path: str) -> list[dict[str, Any]]:
        """Get tools exposed by an MCP server."""
        try:
            client = await self._get_client()
            response = await client.get(f"/api/servers/{path.lstrip('/')}/tools")
            if response.status_code == 404:
                return []
            response.raise_for_status()
            data = response.json()
            return data.get("tools", [])
        except Exception as e:
            logger.error(f"Failed to get tools for {path}: {e}")
            return []


# Global instance
mcp_client = MCPRegistryClient()
