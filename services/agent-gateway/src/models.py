"""Pydantic models for Agent Gateway - A2A protocol compliant."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl


class AgentProvider(BaseModel):
    """Agent provider information."""

    organization: str
    url: Optional[HttpUrl] = None


class SkillInputMode(str, Enum):
    """Supported input modes for skills."""

    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"
    FILE = "file"
    STREAMING = "streaming"


class SkillOutputMode(str, Enum):
    """Supported output modes for skills."""

    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"
    FILE = "file"
    STREAMING = "streaming"


class Skill(BaseModel):
    """A2A Agent Skill definition."""

    id: str
    name: str
    description: str
    input_modes: list[SkillInputMode] = Field(default_factory=lambda: [SkillInputMode.TEXT])
    output_modes: list[SkillOutputMode] = Field(default_factory=lambda: [SkillOutputMode.TEXT])
    parameters: Optional[dict[str, Any]] = None


class SecurityScheme(BaseModel):
    """Security scheme for agent authentication."""

    type: str  # bearer, oauth2, apiKey
    scheme: Optional[str] = None
    bearer_format: Optional[str] = None
    flows: Optional[dict[str, Any]] = None


class AgentCard(BaseModel):
    """A2A Agent Card - the core discovery document."""

    # Required fields
    name: str
    description: str
    url: HttpUrl
    path: str = Field(description="Unique path identifier, e.g., /code-reviewer")

    # Protocol
    protocol_version: str = "1.0.0"
    version: str = "1.0.0"

    # Provider
    provider: Optional[AgentProvider] = None

    # Capabilities
    skills: list[Skill] = Field(default_factory=list)
    streaming: bool = False
    capabilities: dict[str, Any] = Field(default_factory=dict)

    # Security
    security_schemes: dict[str, SecurityScheme] = Field(default_factory=dict)

    # Metadata
    tags: list[str] = Field(default_factory=list)
    license: Optional[str] = None
    visibility: str = "public"  # public, private, group-restricted
    trust_level: str = "unverified"  # unverified, community, verified, trusted

    # Registration
    registered_by: Optional[str] = None
    registered_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_enabled: bool = True

    # Stats
    num_stars: int = 0


class AgentRegistrationRequest(BaseModel):
    """Request to register a new agent."""

    name: str
    description: str
    url: HttpUrl
    path: Optional[str] = None  # Auto-generated from name if not provided

    # Optional fields
    protocol_version: str = "1.0.0"
    version: str = "1.0.0"
    provider: Optional[dict[str, str]] = None
    skills: list[dict[str, Any]] = Field(default_factory=list)
    streaming: bool = False
    security_schemes: Optional[dict[str, Any]] = None
    tags: str = ""  # Comma-separated
    license: Optional[str] = None
    visibility: str = "public"


class LocalModelConfig(BaseModel):
    """Configuration for a local Ollama model."""

    name: str
    model_id: str  # Ollama model name, e.g., qwen3:30b
    description: str
    capabilities: list[str] = Field(default_factory=list)  # coding, reasoning, chat, tools
    context_length: int = 8192
    is_default: bool = False


class AgentInfo(BaseModel):
    """Summary info for agent listings."""

    name: str
    description: str
    path: str
    url: str
    tags: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    num_skills: int = 0
    is_enabled: bool = True
    provider: Optional[str] = None
    streaming: bool = False
    trust_level: str = "unverified"
    model_backend: Optional[str] = None  # ollama, remote, hybrid


class DiscoveryQuery(BaseModel):
    """Query for agent/skill discovery."""

    query: str  # Natural language or skill name
    skills: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    require_local: bool = False  # Only return agents with local model support
    max_results: int = 10
