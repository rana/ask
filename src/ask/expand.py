"""Reference expansion for session files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import httpx
from markdownify import markdownify
from readability import Document

from ask.filter import filter_content, should_filter
from ask.languages import language_for
from ask.patterns import resolve_file_path, should_exclude
from ask.types import Config

# Zero-width space for escaping brackets
ZWS = "\u200b"


def natural_sort_key(path: Path) -> tuple[float, str]:
    """Sort key that orders numeric prefixes naturally.

    Files sort by:
    1. Leading numeric prefix (as integer, inf if none)
    2. Full filename (as string, for tiebreaker)

    Examples:
        1-intro.md → (1, "1-intro.md")
        10-end.md → (10, "10-end.md")
        README.md → (inf, "README.md")
    """
    name = path.name
    match = re.match(r"^(\d+)", name)
    if match:
        return (int(match.group(1)), name)
    return (float("inf"), name)


def expand_references(content: str, config: Config) -> tuple[str, int]:
    """Expand all [[ref]] references in content.

    Returns tuple of (expanded_content, file_count).
    """
    pattern = re.compile(r"\[\[([^\]\u200B]+)\]\]")
    expanded = content
    file_count = 0

    for match in pattern.finditer(content):
        ref = match.group(1)
        try:
            text, files = _expand_reference(ref, config)
            expanded = expanded.replace(match.group(0), text, 1)
            file_count += files
        except Exception as e:
            error_msg = str(e)
            expanded = expanded.replace(match.group(0), f"\n❌ Error: {ref} - {error_msg}\n", 1)

    return expanded, file_count


def _expand_reference(ref: str, config: Config) -> tuple[str, int]:
    """Expand a single reference."""
    if _is_url(ref):
        return _expand_url(ref, config)

    is_recursive = ref.endswith("/**/")
    is_directory = ref.endswith("/") or is_recursive

    # Check if path is actually a directory
    if not is_directory:
        path = Path(ref)
        if path.exists() and path.is_dir():
            return _expand_directory(ref, recursive=False, config=config)

    if is_directory:
        dir_path = re.sub(r"/?(\*\*)?\/?$", "", ref)
        return _expand_directory(dir_path, recursive=is_recursive, config=config)

    return _expand_file(ref, config)


def _is_url(ref: str) -> bool:
    """Check if reference is a URL."""
    return ref.startswith("http://") or ref.startswith("https://")


def _expand_url(url: str, config: Config) -> tuple[str, int]:
    """Expand a URL reference."""
    if not config.web:
        return f"[{ZWS}[{url}]{ZWS}]", 0

    response = httpx.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; ask-cli/1.0)",
            "Accept": "text/html,application/xhtml+xml,text/plain,text/markdown",
        },
        follow_redirects=True,
        timeout=30.0,
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    text = response.text

    if "text/plain" in content_type or "text/markdown" in content_type:
        title = None
        content = text
    elif "text/html" in content_type:
        title, content = _parse_html(text)
    else:
        title = None
        content = text

    lines = [f"<!-- url: {url} -->"]
    if title:
        lines.extend(["", f"# {title}"])
    lines.extend(["", content, "", "<!-- /url -->"])

    return "\n" + "\n".join(lines) + "\n", 1


def _parse_html(html: str) -> tuple[str | None, str]:
    """Parse HTML and extract readable content as markdown."""
    doc = Document(html)
    # Cast untyped library returns at boundary
    title = cast(str | None, doc.title())
    content_html = cast(str, doc.summary())

    # Convert to markdown
    content: str = markdownify(content_html, heading_style="ATX", code_language="")

    return title if title else None, content.strip()


def expand_file(path: str, config: Config) -> tuple[str, int]:
    """Expand a single file reference (public API for refresh)."""
    return _expand_file(path, config)


def expand_directory(path: str, recursive: bool, config: Config) -> tuple[str, int]:
    """Expand a directory reference (public API for refresh)."""
    return _expand_directory(path, recursive, config)


def expand_url(url: str, config: Config) -> tuple[str, int]:
    """Expand a URL reference (public API for refresh)."""
    return _expand_url(url, config)


def _expand_file(path: str, config: Config) -> tuple[str, int]:
    """Expand a single file reference."""
    resolved_path = resolve_file_path(path)

    # Check if binary
    if _is_binary_file(resolved_path):
        raise ValueError("Binary file")

    content = resolved_path.read_text(encoding="utf-8")

    # Apply filtering if enabled
    if should_filter(config.filter):
        content = filter_content(content, str(resolved_path))

    # Escape brackets
    content = content.replace("[[", f"[{ZWS}[")
    content = content.replace("]]", f"]{ZWS}]")

    lang = language_for(str(resolved_path))
    fence = _fence_for(content)

    lines = [
        f"<!-- file: {resolved_path} -->",
        f"### {resolved_path}",
        f"{fence}{lang}",
        content,
        fence,
        "<!-- /file -->",
    ]

    return "\n" + "\n".join(lines) + "\n", 1


def _expand_directory(path: str, recursive: bool, config: Config) -> tuple[str, int]:
    """Expand a directory reference."""
    dir_path = Path(path)
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {path}")

    exclude = config.exclude if config.exclude is not None else Config.default_exclude()

    sections: list[str] = []
    file_count = 0
    has_subdirs = False

    # Check for subdirectories if non-recursive
    if not recursive:
        for entry in dir_path.iterdir():
            if should_exclude(str(entry), exclude):
                continue
            if entry.is_dir():
                has_subdirs = True
                break

    # Collect files with natural sort
    if recursive:
        file_paths = sorted(dir_path.rglob("*"), key=natural_sort_key)
    else:
        file_paths = sorted(dir_path.glob("*"), key=natural_sort_key)

    for file_path in file_paths:
        if not file_path.is_file():
            continue
        if should_exclude(str(file_path), exclude):
            continue

        try:
            text, _ = _expand_file(str(file_path), config)
            sections.append(text)
            file_count += 1
        except Exception:
            # Skip files that can't be expanded
            pass

    if not sections:
        if has_subdirs:
            return (
                f"\n### {path}/\n\n*(contains only subdirectories - "
                f"use [{ZWS}[{path}/**/]{ZWS}] for recursive)*\n",
                0,
            )
        return f"\n### {path}/\n\n*(empty directory)*\n", 0

    content = "".join(sections)
    marker = "/**/" if recursive else "/"
    wrapped = f"<!-- dir: {path}{marker} -->\n{content.strip()}\n<!-- /dir -->"

    return wrapped, file_count


def _is_binary_file(path: Path) -> bool:
    """Check if a file is binary."""
    with path.open("rb") as f:
        preview = f.read(512)
    return b"\x00" in preview


def _fence_for(content: str) -> str:
    """Get the appropriate code fence for content."""
    max_length = 2
    for match in re.finditer(r"`{3,}", content):
        max_length = max(max_length, len(match.group(0)))
    return "`" * (max_length + 1)
