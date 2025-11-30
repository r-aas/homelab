"""Agent Gateway - A2A Agent Registry with MCP integration and local model support."""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import JSONResponse

from agent_service import agent_service
from config import settings
from mcp_client import mcp_client
from models import AgentCard, AgentInfo, AgentRegistrationRequest, DiscoveryQuery
from ollama_service import ollama_service

# Initialize OpenLLMetry tracing before other imports that might be instrumented
if settings.tracing_enabled:
    from traceloop.sdk import Traceloop

    # Set OTLP endpoint via environment (traceloop uses this)
    os.environ.setdefault("TRACELOOP_BASE_URL", settings.otlp_endpoint)

    Traceloop.init(
        app_name=settings.service_name,
        disable_batch=False,  # Batch traces for efficiency
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Agent Gateway starting up...")

    # Log tracing status
    if settings.tracing_enabled:
        logger.info(f"OpenLLMetry tracing enabled, sending to {settings.otlp_endpoint}")
    else:
        logger.info("Tracing disabled")

    # Initialize agent service
    agent_service.initialize()

    # Discover local models
    models = await ollama_service.discover_models()
    logger.info(f"Found {len(models)} local Ollama models")

    # Check MCP Registry connectivity
    mcp_healthy = await mcp_client.health_check()
    if mcp_healthy:
        logger.info("Connected to MCP Registry")
    else:
        logger.warning("MCP Registry not available")

    yield

    # Cleanup
    await mcp_client.close()
    logger.info("Agent Gateway shut down")


app = FastAPI(
    title="Agent Gateway",
    description="A2A Agent Registry with MCP integration and local model support",
    version="0.1.0",
    lifespan=lifespan,
)


# =============================================================================
# Health & Discovery
# =============================================================================


@app.get("/health")
async def health():
    """Health check endpoint."""
    ollama_available = await ollama_service.is_available()
    mcp_available = await mcp_client.health_check()

    return {
        "status": "healthy",
        "ollama": "connected" if ollama_available else "unavailable",
        "mcp_registry": "connected" if mcp_available else "unavailable",
        "agents": len(agent_service.list_agents()),
        "tracing": "enabled" if settings.tracing_enabled else "disabled",
    }


@app.get("/.well-known/agent.json")
async def agent_card():
    """Return this gateway's own agent card for A2A discovery."""
    return {
        "name": "Agent Gateway",
        "description": "Central agent registry with MCP integration and local model support",
        "url": f"http://{settings.host}:{settings.port}",
        "protocolVersion": "1.0.0",
        "skills": [
            {
                "id": "discover-agents",
                "name": "Discover Agents",
                "description": "Find agents by skills or natural language query",
            },
            {
                "id": "discover-tools",
                "name": "Discover Tools",
                "description": "Find MCP tools from registered servers",
            },
            {
                "id": "local-inference",
                "name": "Local Inference",
                "description": "Run inference on local Ollama models",
            },
        ],
    }


# =============================================================================
# Agent Management
# =============================================================================


@app.post("/api/agents/register", status_code=status.HTTP_201_CREATED)
async def register_agent(request: AgentRegistrationRequest):
    """Register a new A2A agent."""
    try:
        agent = agent_service.register(request)
        return {
            "message": "Agent registered successfully",
            "agent": {
                "name": agent.name,
                "path": agent.path,
                "url": str(agent.url),
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@app.get("/api/agents")
async def list_agents(
    enabled_only: bool = Query(False),
    query: Optional[str] = Query(None),
) -> dict[str, Any]:
    """List all registered agents."""
    agents = agent_service.list_agents(enabled_only=enabled_only)

    # Simple text search if query provided
    if query:
        query_lower = query.lower()
        agents = [
            a
            for a in agents
            if query_lower in a.name.lower()
            or query_lower in a.description.lower()
            or any(query_lower in t.lower() for t in a.tags)
        ]

    return {
        "agents": [agent_service.to_info(a).model_dump() for a in agents],
        "total": len(agents),
    }


@app.get("/api/agents/{path:path}")
async def get_agent(path: str) -> dict[str, Any]:
    """Get agent by path."""
    agent = agent_service.get(path)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {path}")
    return agent.model_dump(mode="json")


@app.put("/api/agents/{path:path}")
async def update_agent(path: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Update an existing agent."""
    try:
        agent = agent_service.update(path, updates)
        return agent.model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/api/agents/{path:path}")
async def delete_agent(path: str):
    """Delete an agent."""
    if not agent_service.delete(path):
        raise HTTPException(status_code=404, detail=f"Agent not found: {path}")
    return JSONResponse(status_code=204, content=None)


@app.post("/api/agents/{path:path}/toggle")
async def toggle_agent(path: str, enabled: bool = Query(...)):
    """Enable or disable an agent."""
    if not agent_service.toggle(path, enabled):
        raise HTTPException(status_code=404, detail=f"Agent not found: {path}")
    return {"path": path, "enabled": enabled}


# =============================================================================
# Discovery (Unified MCP + Agents)
# =============================================================================


@app.post("/api/discover")
async def discover(query: DiscoveryQuery) -> dict[str, Any]:
    """Unified discovery across agents, MCP servers, and local models."""
    results = {
        "agents": [],
        "mcp_servers": [],
        "local_models": [],
    }

    # Search local agents
    agents = agent_service.list_agents(enabled_only=True)
    query_lower = query.query.lower()

    for agent in agents:
        searchable = f"{agent.name} {agent.description} {' '.join(agent.tags)}"
        skill_names = [s.name.lower() for s in agent.skills]

        # Match by query text or requested skills
        matches_query = query_lower in searchable.lower()
        matches_skills = any(s.lower() in skill_names for s in query.skills)

        if matches_query or matches_skills or not query.query:
            results["agents"].append(agent_service.to_info(agent).model_dump())

    # Search MCP Registry
    if not query.require_local:
        try:
            mcp_results = await mcp_client.search(query.query, max_results=query.max_results)
            results["mcp_servers"] = mcp_results
        except Exception as e:
            logger.error(f"MCP search failed: {e}")

    # Include local models if relevant
    if query.require_local or "local" in query_lower or "ollama" in query_lower:
        models = await ollama_service.discover_models()
        results["local_models"] = [m.model_dump() for m in models]

    return results


@app.get("/api/tools")
async def list_tools() -> dict[str, Any]:
    """List all available tools from MCP servers."""
    servers = await mcp_client.list_servers()
    all_tools = []

    for server in servers:
        server_path = server.get("path", "")
        tools = await mcp_client.get_server_tools(server_path)
        for tool in tools:
            tool["server"] = server_path
            all_tools.append(tool)

    return {"tools": all_tools, "total": len(all_tools)}


# =============================================================================
# Local Model Inference
# =============================================================================


@app.get("/api/models")
async def list_models() -> dict[str, Any]:
    """List available local Ollama models."""
    models = await ollama_service.discover_models()
    return {
        "models": [m.model_dump() for m in models],
        "default": settings.default_model,
        "available": await ollama_service.is_available(),
    }


@app.post("/api/chat")
async def chat(
    messages: list[dict[str, str]],
    model: Optional[str] = None,
    tools: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Chat with a local Ollama model."""
    model = model or settings.default_model

    if not await ollama_service.is_available():
        raise HTTPException(status_code=503, detail="Ollama not available")

    try:
        response = await ollama_service.chat(model=model, messages=messages, tools=tools)
        # Convert response object to dict if needed
        if hasattr(response, "model_dump"):
            return response.model_dump()
        elif hasattr(response, "__dict__"):
            return dict(response)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Main
# =============================================================================


def main():
    """Run the Agent Gateway server."""
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
