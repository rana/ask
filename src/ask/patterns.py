"""Path pattern matching for exclusion."""

from __future__ import annotations

import fnmatch
from pathlib import Path


def should_exclude(path: str, patterns: list[str]) -> bool:
    """Check if a path should be excluded based on patterns."""
    normalized_path = path.replace("\\", "/")

    for pattern in patterns:
        # Try direct glob match
        if fnmatch.fnmatch(normalized_path, pattern):
            return True

        # Check if any path segment matches the pattern base
        segments = normalized_path.split("/")
        pattern_base = pattern.replace("/**", "").replace("/*", "").rstrip("/")

        if pattern_base in segments:
            return True

        # Check if path is under an excluded directory
        if pattern.endswith("/**"):
            dir_pattern = pattern[:-3]  # Remove /**
            if normalized_path.startswith(dir_pattern + "/") or normalized_path == dir_pattern:
                return True

    return False


def resolve_file_path(path: str) -> Path:
    """Resolve a file path, trying case-insensitive match if needed."""
    file_path = Path(path)
    if file_path.exists():
        return file_path

    # Try case-insensitive match
    parent = file_path.parent
    if not parent.exists():
        raise FileNotFoundError(f"File not found: {path}")

    filename = file_path.name.lower()
    for entry in parent.iterdir():
        if entry.name.lower() == filename:
            return entry

    raise FileNotFoundError(f"File not found: {path}")
