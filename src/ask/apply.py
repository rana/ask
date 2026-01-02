"""Apply extracted files and commands to workspace."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ask.errors import AskError
from ask.extract import CommandBlock, FileBlock, extract_command_blocks, extract_file_blocks
from ask.parser import find_input_marker
from ask.session import read_session
from ask.workspace import find_workspace, resolve_path


@dataclass
class FileResult:
    """Result of writing a file."""

    path: str
    action: str  # "created" or "updated"
    size: int
    error: str | None = None


@dataclass
class CommandResult:
    """Result of executing a command."""

    command: str
    status: str  # "OK" or "FAIL"
    output: str | None = None


@dataclass
class ApplyResult:
    """Result of apply operation."""

    file_results: list[FileResult]
    command_results: list[CommandResult]
    status: str  # "OK" or "PARTIAL"


def apply_session(
    session_path: str,
    dry_run: bool = False,
    apply_files: bool = True,
    apply_commands: bool = True,
) -> ApplyResult:
    """Apply files and commands from last AI turn.

    Args:
        session_path: Path to session file
        dry_run: If True, preview without writing/executing
        apply_files: If True, extract and write files
        apply_commands: If True, execute commands

    Returns:
        ApplyResult with file and command results
    """
    # Read session and find last AI turn
    session = read_session(session_path)

    # Find last AI turn
    ai_turn = None
    for turn in reversed(session.turns):
        if turn.role == "AI":
            ai_turn = turn
            break

    if ai_turn is None:
        raise AskError("No AI response to apply", "Run 'ask' first to get an AI response")

    # Read session content for workspace marker
    session_content = Path(session_path).read_text(encoding="utf-8")
    workspace = find_workspace(session_content)

    # Extract blocks from AI turn
    file_blocks = extract_file_blocks(ai_turn.content) if apply_files else []
    command_blocks = extract_command_blocks(ai_turn.content) if apply_commands else []

    if not file_blocks and not command_blocks:
        raise AskError(
            "No files or commands to apply",
            "AI response has no <!-- file: --> or <!-- ask:command --> blocks",
        )

    # Apply files
    file_results: list[FileResult] = []
    for block in file_blocks:
        result = _write_file(block, workspace, dry_run)
        file_results.append(result)

    # Apply commands
    command_results: list[CommandResult] = []
    if apply_commands and command_blocks:
        for block in command_blocks:
            result = _execute_command(block, workspace, dry_run)
            command_results.append(result)
            # Stop on failure
            if result.status == "FAIL":
                break

    # Determine overall status
    has_failure = any(r.error for r in file_results) or any(
        r.status == "FAIL" for r in command_results
    )
    status = "PARTIAL" if has_failure else "OK"

    return ApplyResult(
        file_results=file_results,
        command_results=command_results,
        status=status,
    )


def _write_file(block: FileBlock, workspace: Path | None, dry_run: bool) -> FileResult:
    """Write a file block to disk."""
    resolved = resolve_path(block.path, workspace)

    # Determine action
    action = "updated" if resolved.exists() else "created"
    size = len(block.content.encode("utf-8"))

    if dry_run:
        return FileResult(path=block.path, action=action, size=size)

    try:
        # Create parent directories
        resolved.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        resolved.write_text(block.content, encoding="utf-8")

        return FileResult(path=block.path, action=action, size=size)
    except Exception as e:
        return FileResult(path=block.path, action="FAILED", size=0, error=str(e))


def _execute_command(block: CommandBlock, workspace: Path | None, dry_run: bool) -> CommandResult:
    """Execute a command block."""
    if dry_run:
        return CommandResult(command=block.command, status="OK")

    try:
        # Determine working directory
        cwd = workspace if workspace else Path.cwd()

        # Execute command
        result = subprocess.run(
            block.command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode == 0:
            return CommandResult(command=block.command, status="OK")
        else:
            # Combine stdout and stderr for error output
            output = result.stdout + result.stderr
            return CommandResult(command=block.command, status="FAIL", output=output.strip())

    except subprocess.TimeoutExpired:
        return CommandResult(
            command=block.command, status="FAIL", output="Command timed out after 5 minutes"
        )
    except Exception as e:
        return CommandResult(command=block.command, status="FAIL", output=str(e))


def format_applied_block(result: ApplyResult) -> str:
    """Format apply results as markdown block."""
    lines: list[str] = []

    # Opening marker with status
    if result.status == "PARTIAL":
        lines.append("<!-- ask:applied status=PARTIAL -->")
    else:
        lines.append("<!-- ask:applied -->")

    # File results table
    if result.file_results:
        lines.append("| Path | Action | Size |")
        lines.append("|------|--------|------|")
        for fr in result.file_results:
            size_str = _format_size(fr.size) if fr.error is None else fr.error or "error"
            lines.append(f"| {fr.path} | {fr.action} | {size_str} |")

    # Command results table
    if result.command_results:
        if result.file_results:
            lines.append("")  # Blank line between tables
        lines.append("| Command | Status |")
        lines.append("|---------|--------|")
        for cr in result.command_results:
            # Truncate long commands for table
            cmd_display = cr.command if len(cr.command) <= 40 else cr.command[:37] + "..."
            lines.append(f"| {cmd_display} | {cr.status} |")

    # Failed command output
    failed_commands = [cr for cr in result.command_results if cr.status == "FAIL" and cr.output]
    for cr in failed_commands:
        lines.append("")
        # Truncate command for heading
        cmd_display = cr.command if len(cr.command) <= 50 else cr.command[:47] + "..."
        lines.append(f"### {cmd_display}")
        lines.append("```")
        lines.append(cr.output or "")
        lines.append("```")

    lines.append("<!-- /ask:applied -->")

    return "\n".join(lines)


def _format_size(size: int) -> str:
    """Format byte size for display."""
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size // 1024}KB"
    else:
        return f"{size // (1024 * 1024)}MB"


def insert_applied_block(session_path: str, applied_block: str) -> None:
    """Insert applied block before the _ marker in session.

    Inserts after the turn header, before any user text.
    """
    content = Path(session_path).read_text(encoding="utf-8")

    # Find the input marker
    marker_info = find_input_marker(content)
    if marker_info is None:
        raise AskError(
            "No input marker found",
            "Add `_` on its own line in the current human turn",
        )

    line_idx, _ = marker_info
    lines = content.split("\n")

    # Find the start of the current human turn (search backwards from marker)
    turn_start = None
    for i in range(line_idx - 1, -1, -1):
        if lines[i].startswith("# [") and "Human" in lines[i]:
            turn_start = i
            break

    if turn_start is None:
        raise AskError("Cannot find human turn for marker")

    # Insert position is right after turn header (and any blank line)
    insert_pos = turn_start + 1
    while insert_pos < line_idx and lines[insert_pos].strip() == "":
        insert_pos += 1

    # Insert the applied block
    new_lines = lines[:insert_pos] + ["", applied_block, ""] + lines[insert_pos:]

    # Write back
    Path(session_path).write_text("\n".join(new_lines), encoding="utf-8")
