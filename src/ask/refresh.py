"""Refresh expanded references in session files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ask.config import load_config
from ask.expand import expand_directory, expand_file, expand_url
from ask.output import output
from ask.types import Config


@dataclass
class MarkerBlock:
    """A marker block found in content."""

    type: str  # "file", "dir", "url"
    reference: str  # The path or URL
    start: int  # Start position in content
    end: int  # End position in content (inclusive of closing marker)
    is_recursive: bool = False  # For directories


@dataclass
class RefreshResult:
    """Result of a refresh operation."""

    files_refreshed: int
    dirs_refreshed: int
    urls_refreshed: int
    errors: list[str]
    details: list[str]  # What was refreshed


def find_marker_blocks(content: str, include_urls: bool = False) -> list[MarkerBlock]:
    """Find all marker blocks in content.

    Args:
        content: Session content to search
        include_urls: Whether to include URL blocks

    Returns:
        List of MarkerBlock in order of appearance
    """
    blocks: list[MarkerBlock] = []

    # Pattern for file markers: <!-- file: path -->...<!-- /file -->
    file_pattern = re.compile(
        r"(<!-- file: ([^\s>]+) -->)(.*?)(<!-- /file -->)",
        re.DOTALL,
    )

    for match in file_pattern.finditer(content):
        # Skip error markers
        inner_content = match.group(3)
        if inner_content.strip().startswith("❌"):
            continue

        blocks.append(
            MarkerBlock(
                type="file",
                reference=match.group(2),
                start=match.start(),
                end=match.end(),
            )
        )

    # Pattern for directory markers: <!-- dir: path/ --> or <!-- dir: path/**/ -->
    dir_pattern = re.compile(
        r"(<!-- dir: ([^\s>]+?)(/\*\*/|/) -->)(.*?)(<!-- /dir -->)",
        re.DOTALL,
    )

    for match in dir_pattern.finditer(content):
        inner_content = match.group(4)
        if inner_content.strip().startswith("❌"):
            continue

        is_recursive = match.group(3) == "/**/"
        blocks.append(
            MarkerBlock(
                type="dir",
                reference=match.group(2),
                start=match.start(),
                end=match.end(),
                is_recursive=is_recursive,
            )
        )

    # Pattern for URL markers (only if requested)
    if include_urls:
        url_pattern = re.compile(
            r"(<!-- url: ([^\s>]+) -->)(.*?)(<!-- /url -->)",
            re.DOTALL,
        )

        for match in url_pattern.finditer(content):
            inner_content = match.group(3)
            if inner_content.strip().startswith("❌"):
                continue

            blocks.append(
                MarkerBlock(
                    type="url",
                    reference=match.group(2),
                    start=match.start(),
                    end=match.end(),
                )
            )

    # Sort by position
    blocks.sort(key=lambda b: b.start)

    return blocks


def refresh_block(block: MarkerBlock, config: Config) -> str:
    """Re-expand a single marker block.

    Args:
        block: The marker block to refresh
        config: Configuration for expansion

    Returns:
        New expanded content (including markers)

    Raises:
        Exception on expansion failure
    """
    if block.type == "file":
        expanded, _ = expand_file(block.reference, config)
        return expanded.strip()

    elif block.type == "dir":
        expanded, _ = expand_directory(block.reference, block.is_recursive, config)
        return expanded.strip()

    elif block.type == "url":
        expanded, _ = expand_url(block.reference, config)
        return expanded.strip()

    else:
        raise ValueError(f"Unknown block type: {block.type}")


def refresh_content(
    content: str,
    include_urls: bool = False,
    config: Config | None = None,
) -> tuple[str, RefreshResult]:
    """Refresh all marker blocks in content.

    Args:
        content: Session content to refresh
        include_urls: Whether to refresh URL blocks
        config: Configuration (loads default if None)

    Returns:
        Tuple of (new_content, result)
    """
    if config is None:
        config = load_config()

    blocks = find_marker_blocks(content, include_urls=include_urls)

    result = RefreshResult(
        files_refreshed=0,
        dirs_refreshed=0,
        urls_refreshed=0,
        errors=[],
        details=[],
    )

    if not blocks:
        return content, result

    # Process in reverse order to preserve positions
    new_content = content
    for block in reversed(blocks):
        try:
            expanded = refresh_block(block, config)
            new_content = new_content[: block.start] + expanded + new_content[block.end :]

            if block.type == "file":
                result.files_refreshed += 1
                result.details.append(block.reference)
            elif block.type == "dir":
                result.dirs_refreshed += 1
                marker = "/**/" if block.is_recursive else "/"
                result.details.append(f"{block.reference}{marker}")
            elif block.type == "url":
                result.urls_refreshed += 1
                result.details.append(block.reference)

        except FileNotFoundError:
            # Replace with error marker
            error_marker = f"\n❌ Error: {block.reference} - File not found\n"
            new_content = new_content[: block.start] + error_marker + new_content[block.end :]
            result.errors.append(f"{block.reference}: File not found")

        except ValueError as e:
            if "Binary file" in str(e):
                error_marker = f"\n❌ Error: {block.reference} - Binary file\n"
                new_content = new_content[: block.start] + error_marker + new_content[block.end :]
                result.errors.append(f"{block.reference}: Binary file")
            else:
                # Keep old content for other errors
                result.errors.append(f"{block.reference}: {e}")

        except Exception as e:
            # For URLs and other failures, keep old content and log warning
            if block.type == "url":
                result.errors.append(f"{block.reference}: {e} (kept old content)")
            else:
                result.errors.append(f"{block.reference}: {e}")

    return new_content, result


def refresh_session(
    session_path: str,
    include_urls: bool = False,
    dry_run: bool = False,
) -> RefreshResult:
    """Refresh all marker blocks in a session file.

    Args:
        session_path: Path to session file
        include_urls: Whether to refresh URL blocks
        dry_run: If True, don't write changes

    Returns:
        RefreshResult with counts and details
    """
    path = Path(session_path)
    content = path.read_text(encoding="utf-8")

    new_content, result = refresh_content(content, include_urls=include_urls)

    if not dry_run and new_content != content:
        path.write_text(new_content, encoding="utf-8")

    return result


def print_refresh_result(result: RefreshResult, dry_run: bool = False) -> None:
    """Print refresh results to console."""
    total = result.files_refreshed + result.dirs_refreshed + result.urls_refreshed

    if total == 0 and not result.errors:
        output.info("No marker blocks found to refresh")
        return

    # Build summary
    parts: list[str] = []
    if result.files_refreshed > 0:
        count = result.files_refreshed
        parts.append(f"{count} file{'s' if count != 1 else ''}")
    if result.dirs_refreshed > 0:
        count = result.dirs_refreshed
        parts.append(f"{count} director{'ies' if count != 1 else 'y'}")
    if result.urls_refreshed > 0:
        count = result.urls_refreshed
        parts.append(f"{count} URL{'s' if count != 1 else ''}")

    if dry_run:
        if parts:
            output.info(f"Would refresh {', '.join(parts)}:")
            for detail in result.details:
                output.info(f"  {detail}")
    else:
        if parts:
            output.success(f"Refreshed {', '.join(parts)}")
            for detail in result.details:
                output.info(f"  {output.dim('Updated:')} {detail}")

    # Show errors
    for error in result.errors:
        output.warning(error)
