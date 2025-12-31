"""Token estimation utilities."""

from __future__ import annotations

from ask.types import Message


def estimate_tokens(messages: list[Message]) -> int:
    """Estimate token count for messages."""
    char_count = 0

    for message in messages:
        for content in message["content"]:
            char_count += len(content["text"])

    # Rough estimate: ~4 chars per token
    return (char_count + 3) // 4
