"""Type definitions for ask."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict


@dataclass
class Turn:
    """A single turn in a conversation."""

    number: int
    role: Literal["Human", "AI"]
    content: str


@dataclass
class Session:
    """A parsed session containing turns."""

    turns: list[Turn]
    last_human_turn_index: int


class MessageContent(TypedDict):
    """Content block in a message."""

    text: str


class Message(TypedDict):
    """A message for the AI API."""

    role: Literal["user", "assistant"]
    content: list[MessageContent]


@dataclass
class StreamChunk:
    """A chunk from the streaming response."""

    text: str
    tokens: int


@dataclass
class StreamEnd:
    """End of streaming response."""

    total_tokens: int


@dataclass
class StreamError:
    """Error during streaming."""

    error: Exception


StreamEvent = StreamChunk | StreamEnd | StreamError

ModelType = Literal["opus", "sonnet", "haiku"]


@dataclass
class InferenceProfile:
    """AWS Bedrock inference profile."""

    arn: str
    model_id: str


@dataclass
class Config:
    """User configuration."""

    model: ModelType = "sonnet"
    temperature: float = 1.0
    max_tokens: int | None = None
    region: str | None = None
    filter: bool = True
    exclude: list[str] | None = None

    @staticmethod
    def default_exclude() -> list[str]:
        """Return default exclude patterns."""
        return [
            ".git/**",
            "node_modules/**",
            "vendor/**",
            "*.lock",
            "uv.lock",
            "bun.lockb",
            "dist/**",
            "build/**",
            "out/**",
            ".next/**",
            ".nuxt/**",
            "*.min.js",
            "*.min.css",
            "coverage/**",
            "*.test.ts",
            "*.spec.ts",
            ".vscode/**",
            ".DS_Store",
            "Thumbs.db",
            "tmp/**",
            ".env",
            ".env.*",
            "*.pem",
            "*.key",
            ".gitignore",
            ".dockerignore",
            "LICENSE",
            "session.md",
            "__pycache__/**",
            "*.pyc",
            ".venv/**",
            ".pytest_cache/**",
            ".ruff_cache/**",
            ".mypy_cache/**",
        ]


@dataclass
class ExpandedContent:
    """Information about expanded content in a session."""

    type: Literal["directory", "file", "url"]
    pattern: str
    start_line: int
    end_line: int
