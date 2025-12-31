"""Session file parser for ask."""

from __future__ import annotations

import re

from ask.regions import find_excluded_regions, is_in_excluded_region
from ask.types import Turn


def parse_turns(content: str) -> list[Turn]:
    """Parse session content into turns.

    Detects turn headers matching `# [N] Human` or `# [N] AI`,
    excluding headers inside code fences or marker regions.

    AI turns wrapped in 6 backticks are automatically unwrapped.
    """
    lines = content.split("\n")
    regions = find_excluded_regions(lines)

    turn_pattern = re.compile(r"^# \[(\d+)\] (Human|AI)\s*$")

    # Find all turn header positions
    turn_starts: list[tuple[int, int, str]] = []  # (line_index, turn_number, role)

    for i, line in enumerate(lines):
        if is_in_excluded_region(i, regions):
            continue

        match = turn_pattern.match(line)
        if match:
            turn_number = int(match.group(1))
            role = match.group(2)
            turn_starts.append((i, turn_number, role))

    if not turn_starts:
        return []

    # Extract content for each turn
    turns: list[Turn] = []

    for idx, (start_line, turn_number, role) in enumerate(turn_starts):
        # Content starts after the header line
        content_start = start_line + 1

        # Content ends at next turn header or end of file
        content_end = turn_starts[idx + 1][0] if idx + 1 < len(turn_starts) else len(lines)

        # Extract content lines
        content_lines = lines[content_start:content_end]
        turn_content = "\n".join(content_lines)

        # Unwrap AI responses from 6-backtick wrapper
        if role == "AI":
            turn_content = _unwrap_ai_response(turn_content)

        # Strip leading/trailing whitespace but preserve internal structure
        turn_content = turn_content.strip()

        turns.append(Turn(
            number=turn_number,
            role=role,  # type: ignore[arg-type]
            content=turn_content,
        ))

    return turns


def _unwrap_ai_response(content: str) -> str:
    """Unwrap AI response from exactly 6 backticks.

    AI responses are wrapped as:
    ```````markdown
    ``````markdown
    actual content here
    ``````
    ```````

    This function removes the outer wrapper if present.
    """
    lines = content.split("\n")

    # Find opening: line starting with exactly 6 backticks followed by markdown
    opening_pattern = re.compile(r"^`{6}markdown\s*$")
    closing_pattern = re.compile(r"^`{6}\s*$")

    opening_idx: int | None = None
    closing_idx: int | None = None

    # Find first opening
    for i, line in enumerate(lines):
        stripped = line.strip()
        if opening_pattern.match(stripped):
            opening_idx = i
            break

    if opening_idx is None:
        return content

    # Find matching closing (must be exactly 6 backticks)
    for i in range(len(lines) - 1, opening_idx, -1):
        stripped = lines[i].strip()
        if closing_pattern.match(stripped):
            closing_idx = i
            break

    if closing_idx is None:
        return content

    # Extract content between opening and closing
    inner_lines = lines[opening_idx + 1 : closing_idx]
    return "\n".join(inner_lines)


def find_input_marker(content: str) -> tuple[int, int] | None:
    """Find the `_` input marker in content.

    Returns (line_index, char_position) if found, None otherwise.
    The marker must be on its own line, outside code fences and marker blocks.
    """
    lines = content.split("\n")
    regions = find_excluded_regions(lines)

    marker_pattern = re.compile(r"^_\s*$")

    for i, line in enumerate(lines):
        if is_in_excluded_region(i, regions):
            continue

        if marker_pattern.match(line):
            # Calculate character position
            char_pos = sum(len(lines[j]) + 1 for j in range(i))
            return (i, char_pos)

    return None


def count_input_markers(content: str) -> int:
    """Count `_` input markers in content (outside excluded regions)."""
    lines = content.split("\n")
    regions = find_excluded_regions(lines)

    marker_pattern = re.compile(r"^_\s*$")
    count = 0

    for i, line in enumerate(lines):
        if is_in_excluded_region(i, regions):
            continue

        if marker_pattern.match(line):
            count += 1

    return count