"""Workspace resolution for ask apply."""

from __future__ import annotations

import re
from pathlib import Path


def find_workspace(content: str) -> Path | None:
    """Find workspace marker in session content.

    Looks for `<!-- ask:workspace /path/to/project/ -->` at the start of the file.
    Returns the workspace path if found, None otherwise.
    """
    # Pattern to match workspace marker
    pattern = re.compile(r"^<!-- ask:workspace\s+([^\s>]+)\s*-->", re.MULTILINE)

    match = pattern.search(content)
    if match:
        workspace_path = match.group(1)
        return Path(workspace_path)

    return None


def resolve_path(file_path: str, workspace: Path | None) -> Path:
    """Resolve a file path relative to workspace or cwd.

    Resolution order:
    1. Absolute paths → use as-is
    2. Workspace defined → resolve relative to workspace
    3. No workspace → resolve relative to cwd
    """
    path = Path(file_path)

    # Absolute paths are used as-is
    if path.is_absolute():
        return path

    # Relative paths resolve against workspace or cwd
    if workspace is not None:
        return workspace / path
    else:
        return Path.cwd() / path
