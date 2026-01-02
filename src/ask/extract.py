"""Extract file and command blocks from AI responses."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class FileBlock:
    """A file block extracted from AI response."""

    path: str
    content: str


@dataclass
class CommandBlock:
    """A command block extracted from AI response."""

    command: str


def extract_file_blocks(content: str) -> list[FileBlock]:
    """Extract all file blocks from content.

    Parses `<!-- file: path -->...<!-- /file -->` blocks and extracts
    the content from the inner code fence.
    """
    blocks: list[FileBlock] = []

    # Pattern to match file markers with content between them
    file_pattern = re.compile(
        r"<!-- file: ([^\s>]+) -->\s*\n"  # Opening marker with path
        r"(.*?)"  # Content (non-greedy)
        r"<!-- /file -->",  # Closing marker
        re.DOTALL,
    )

    for match in file_pattern.finditer(content):
        path = match.group(1)
        raw_content = match.group(2)

        # Extract content from code fence
        extracted = _extract_fence_content(raw_content)
        if extracted is not None:
            blocks.append(FileBlock(path=path, content=extracted))

    return blocks


def extract_command_blocks(content: str) -> list[CommandBlock]:
    """Extract all command blocks from content.

    Parses `<!-- ask:command -->...<!-- /ask:command -->` blocks and extracts
    the command from the inner code fence.
    """
    blocks: list[CommandBlock] = []

    # Pattern to match command markers with content between them
    cmd_pattern = re.compile(
        r"<!-- ask:command -->\s*\n"  # Opening marker
        r"(.*?)"  # Content (non-greedy)
        r"<!-- /ask:command -->",  # Closing marker
        re.DOTALL,
    )

    for match in cmd_pattern.finditer(content):
        raw_content = match.group(1)

        # Extract command from code fence
        extracted = _extract_fence_content(raw_content)
        if extracted is not None:
            # Strip and take the command (may be multiline)
            command = extracted.strip()
            if command:
                blocks.append(CommandBlock(command=command))

    return blocks


def _extract_fence_content(raw: str) -> str | None:
    """Extract content from inside a code fence.

    Handles fences of varying backtick lengths.
    Returns None if no valid fence found.
    """
    # Match opening fence with optional language hint
    fence_pattern = re.compile(
        r"^(`{3,})(\w*)\s*\n"  # Opening fence
        r"(.*?)"  # Content
        r"^\1\s*$",  # Closing fence (same length)
        re.MULTILINE | re.DOTALL,
    )

    match = fence_pattern.search(raw)
    if match:
        content = match.group(3)
        # Remove trailing newline if present
        if content.endswith("\n"):
            content = content[:-1]
        return content

    return None
