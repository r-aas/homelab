"""Agent registry service with A2A protocol support."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import settings
from models import AgentCard, AgentInfo, AgentRegistrationRequest, Skill

logger = logging.getLogger(__name__)


def _path_to_filename(path: str) -> str:
    """Convert agent path to safe filename."""
    normalized = path.lstrip("/").replace("/", "_")
    if not normalized.endswith("_agent.json"):
        normalized += "_agent.json"
    return normalized


def _normalize_path(path: Optional[str], agent_name: Optional[str] = None) -> str:
    """Normalize agent path format."""
    if path is None:
        if not agent_name:
            raise ValueError("Path or agent_name required")
        path = agent_name.lower().replace(" ", "-")

    if not path.startswith("/"):
        path = "/" + path

    return path.rstrip("/") if len(path) > 1 else path


class AgentService:
    """Service for managing A2A agent registration and discovery."""

    def __init__(self):
        """Initialize agent service."""
        self._agents: dict[str, AgentCard] = {}
        self._state: dict[str, list[str]] = {"enabled": [], "disabled": []}
        self._data_dir = Path(settings.data_dir) / "agents"

    def initialize(self) -> None:
        """Load agents from disk."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._load_agents()
        self._load_state()
        logger.info(f"Loaded {len(self._agents)} agents")

    def _load_agents(self) -> None:
        """Load agent cards from disk."""
        for file in self._data_dir.glob("*_agent.json"):
            try:
                with open(file) as f:
                    data = json.load(f)
                agent = AgentCard(**data)
                self._agents[agent.path] = agent
            except Exception as e:
                logger.error(f"Failed to load {file}: {e}")

    def _load_state(self) -> None:
        """Load agent enable/disable state."""
        state_file = self._data_dir / "state.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    self._state = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load state: {e}")

        # Initialize state for new agents
        for path in self._agents:
            if path not in self._state["enabled"] and path not in self._state["disabled"]:
                self._state["enabled"].append(path)

    def _save_state(self) -> None:
        """Persist state to disk."""
        state_file = self._data_dir / "state.json"
        try:
            with open(state_file, "w") as f:
                json.dump(self._state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _save_agent(self, agent: AgentCard) -> bool:
        """Save agent card to disk."""
        try:
            filename = _path_to_filename(agent.path)
            file_path = self._data_dir / filename
            with open(file_path, "w") as f:
                json.dump(agent.model_dump(mode="json"), f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save agent: {e}")
            return False

    def register(self, request: AgentRegistrationRequest, registered_by: str = "system") -> AgentCard:
        """Register a new agent."""
        path = _normalize_path(request.path, request.name)

        if path in self._agents:
            raise ValueError(f"Agent already exists at path: {path}")

        # Parse skills
        skills = []
        for skill_data in request.skills:
            skills.append(Skill(**skill_data))

        # Parse tags
        tags = [t.strip() for t in request.tags.split(",") if t.strip()]

        # Create agent card
        now = datetime.now(timezone.utc)
        agent = AgentCard(
            name=request.name,
            description=request.description,
            url=request.url,
            path=path,
            protocol_version=request.protocol_version,
            version=request.version,
            skills=skills,
            streaming=request.streaming,
            tags=tags,
            license=request.license,
            visibility=request.visibility,
            registered_by=registered_by,
            registered_at=now,
            updated_at=now,
            is_enabled=True,
        )

        # Save and register
        if not self._save_agent(agent):
            raise ValueError("Failed to save agent")

        self._agents[path] = agent
        self._state["enabled"].append(path)
        self._save_state()

        logger.info(f"Registered agent: {agent.name} at {path}")
        return agent

    def get(self, path: str) -> Optional[AgentCard]:
        """Get agent by path."""
        path = _normalize_path(path)
        return self._agents.get(path)

    def list_agents(self, enabled_only: bool = False) -> list[AgentCard]:
        """List all agents."""
        agents = list(self._agents.values())
        if enabled_only:
            agents = [a for a in agents if a.path in self._state["enabled"]]
        return agents

    def update(self, path: str, updates: dict) -> AgentCard:
        """Update an existing agent."""
        path = _normalize_path(path)
        agent = self._agents.get(path)
        if not agent:
            raise ValueError(f"Agent not found: {path}")

        # Merge updates
        agent_dict = agent.model_dump()
        agent_dict.update(updates)
        agent_dict["updated_at"] = datetime.now(timezone.utc)

        updated = AgentCard(**agent_dict)
        self._save_agent(updated)
        self._agents[path] = updated

        return updated

    def delete(self, path: str) -> bool:
        """Delete an agent."""
        path = _normalize_path(path)
        if path not in self._agents:
            return False

        # Remove file
        filename = _path_to_filename(path)
        file_path = self._data_dir / filename
        if file_path.exists():
            file_path.unlink()

        # Remove from registry
        del self._agents[path]

        # Update state
        if path in self._state["enabled"]:
            self._state["enabled"].remove(path)
        if path in self._state["disabled"]:
            self._state["disabled"].remove(path)
        self._save_state()

        return True

    def toggle(self, path: str, enabled: bool) -> bool:
        """Enable or disable an agent."""
        path = _normalize_path(path)
        if path not in self._agents:
            return False

        if enabled:
            if path in self._state["disabled"]:
                self._state["disabled"].remove(path)
            if path not in self._state["enabled"]:
                self._state["enabled"].append(path)
        else:
            if path in self._state["enabled"]:
                self._state["enabled"].remove(path)
            if path not in self._state["disabled"]:
                self._state["disabled"].append(path)

        self._save_state()
        return True

    def is_enabled(self, path: str) -> bool:
        """Check if agent is enabled."""
        path = _normalize_path(path)
        return path in self._state["enabled"]

    def to_info(self, agent: AgentCard) -> AgentInfo:
        """Convert AgentCard to AgentInfo summary."""
        return AgentInfo(
            name=agent.name,
            description=agent.description,
            path=agent.path,
            url=str(agent.url),
            tags=agent.tags,
            skills=[s.name for s in agent.skills],
            num_skills=len(agent.skills),
            is_enabled=self.is_enabled(agent.path),
            provider=agent.provider.organization if agent.provider else None,
            streaming=agent.streaming,
            trust_level=agent.trust_level,
        )


# Global instance
agent_service = AgentService()
