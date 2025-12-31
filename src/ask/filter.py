"""Content filtering to remove comments and headers."""

from __future__ import annotations

import re
from dataclasses import dataclass

PRESERVE_PATTERNS = [
    re.compile(r"^#!"),
    re.compile(r"^//\s*@ts-"),
    re.compile(r"^//go:"),
    re.compile(r"^#\s*-\*-.*-\*-"),
    re.compile(r"^#\s*frozen_string_literal"),
    re.compile(r'^[\'"]use strict[\'"];?$'),
]

HEADER_PATTERNS = [
    {"start": re.compile(r"^/\*+"), "end": re.compile(r"\*+/")},
    {"start": re.compile(r"^<!--"), "end": re.compile(r"-->")},
    {"start": re.compile(r'^"""'), "end": re.compile(r'"""')},
    {"start": re.compile(r"^'''"), "end": re.compile(r"'''")},
]


@dataclass
class CommentStyle:
    """Comment style for a language."""

    line: str | None = None
    block_start: str | None = None
    block_end: str | None = None


COMMENT_PATTERNS = {
    "c_style": CommentStyle(line="//", block_start="/*", block_end="*/"),
    "hash": CommentStyle(line="#"),
    "sql": CommentStyle(line="--"),
    "html": CommentStyle(block_start="<!--", block_end="-->"),
}


def should_filter(config_filter: bool | None) -> bool:
    """Check if content filtering is enabled."""
    return config_filter if config_filter is not None else True


def filter_content(content: str, file_path: str) -> str:
    """Filter comments and headers from content."""
    content = _strip_headers(content)
    content = _strip_comments(content, file_path)
    # Collapse multiple blank lines
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def _strip_headers(content: str) -> str:
    """Remove file headers (license blocks, docstrings, etc.)."""
    trimmed = content.lstrip()

    for pattern in HEADER_PATTERNS:
        if pattern["start"].match(trimmed):
            end_match = pattern["end"].search(trimmed)
            if end_match:
                after_header = trimmed[end_match.end() :]
                return _strip_headers(after_header)

    return content


def _strip_comments(content: str, file_path: str) -> str:
    """Remove comments from content."""
    style = _detect_comment_style(content, file_path)
    if not style:
        return content

    lines = content.split("\n")
    result: list[str] = []
    in_block = False

    for line in lines:
        # Check if line should be preserved
        stripped = line.strip()
        if any(p.match(stripped) for p in PRESERVE_PATTERNS):
            result.append(line)
            continue

        # Handle block comments
        if style.block_start and not in_block and stripped.startswith(style.block_start):
            in_block = True
            continue

        if in_block and style.block_end and style.block_end in line:
            in_block = False
            continue

        if in_block:
            continue

        # Handle line comments
        if style.line:
            comment_idx = line.find(style.line)
            if comment_idx == 0:
                continue
            if comment_idx > 0:
                before = line[:comment_idx].rstrip()
                if before:
                    result.append(before)
                continue

        result.append(line)

    return "\n".join(result)


def _detect_comment_style(content: str, file_path: str) -> CommentStyle | None:
    """Detect the comment style for a file."""
    # Check content patterns
    if "//" in content and ("/*" in content or re.search(r"\.(js|ts|java|c|cpp|go)$", file_path)):
        return COMMENT_PATTERNS["c_style"]

    if re.search(r"^\s*#", content, re.MULTILINE) and re.search(
        r"\.(py|rb|sh|yaml|yml)$", file_path
    ):
        return COMMENT_PATTERNS["hash"]

    if "<!--" in content:
        return COMMENT_PATTERNS["html"]

    if "--" in content and file_path.endswith(".sql"):
        return COMMENT_PATTERNS["sql"]

    # Check by extension
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""

    c_style_exts = {"js", "ts", "jsx", "tsx", "java", "c", "cpp", "cs", "go", "swift", "kt", "rs"}
    if ext in c_style_exts:
        return COMMENT_PATTERNS["c_style"]

    hash_exts = {"py", "rb", "sh", "bash", "zsh", "yaml", "yml", "toml"}
    if ext in hash_exts:
        return COMMENT_PATTERNS["hash"]

    return None
