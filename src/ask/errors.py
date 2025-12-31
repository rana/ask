"""Error types for ask."""

from __future__ import annotations


class AskError(Exception):
    """Base error for ask operations."""

    def __init__(self, message: str, help_text: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.help_text = help_text

    def __str__(self) -> str:
        if self.help_text:
            return f"{self.message}\n\n{self.help_text}"
        return self.message

    @classmethod
    def from_exception(cls, error: Exception) -> AskError:
        """Convert a generic exception to an AskError."""
        message = str(error)

        if "CredentialsProviderError" in message or "NoCredentialsError" in message:
            return cls("AWS credentials not configured", "Run: aws configure")

        if "ValidationException" in message:
            return cls("Invalid request to Bedrock", "Check your AWS region and model access")

        if "maximum tokens" in message.lower():
            return cls("Token limit exceeded", "Try a shorter conversation or different model")

        if "conversation must start with a user message" in message.lower():
            return cls(
                "Invalid conversation format",
                "Check session.md has proper Human/AI structure",
            )

        if "timed out" in message.lower() or "timeout" in message.lower():
            return cls(
                "Request timed out after 5 minutes",
                "Try a shorter conversation or simpler request",
            )

        return cls(message)


class ParseError(AskError):
    """Error parsing session file."""

    pass


class RefExpansionError(AskError):
    """Error expanding a reference."""

    pass


class ConfigError(AskError):
    """Error with configuration."""

    pass
