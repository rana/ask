# [1] Human

I'm building **Ask** (system name) with **`ask`** as the CLI. AI is the primary implementer.

**Repo:** https://github.com/rana/ask

**Workspace Root:** /home/rana/prj/ask/

## [1.1] Authoritative Design Docs

[[/home/rana/prj/chats/ask/v3/design/**/]]

## [1.2] Source Code Reference

[[/home/rana/prj/ask/**/]]

## [1.3] Core Philosophy

**Your role as AI:**
- AI as designer: Propose clean solutions within spec constraints
- AI as implementer: Write complete, working code

**ask v3 principles:**
- Session file is authoritative: No separate state. Parse fresh each time.
- Machine output is visible: If `ask apply` writes files, the session shows what was written.
- AI context is derivable: What AI sees can be reconstructed from the session.
- Markers are symmetric: Same `<!-- file: -->` format for expansion and extraction.
- Preserve user content: Never overwrite user text. Insert at designated points only.

**Development principles:**
- Explicit over implicit, simple over clever
- Zero magic: no hidden state, no surprises
- Functional Core, Imperative Shell: Logic (parsing, expanding) is pure; I/O is pushed to boundaries.
- Fail informatively: errors explain what went wrong and how to fix it
- Simple > Complex, but Right > Simple

## [1.4] Collaboration Patterns

**Patterns:**
- Implement → Test → Commit cycles
- Complete files, not fragments
- Test each command before moving on
- Commit working code before adding complexity
- Start with the simplest implementation that could work
- Lock outputs early: capture golden fixtures at first green
- Contract correctness before breadth: stable interfaces before new features
- Phase Review Checklist before committing
- Fix lint/type errors iteratively with human review
- Discuss design tradeoffs before implementing
- Consolidate shared test utilities to conftest.py

**Preferences:**
- Declarative > Imperative
- Data > Code
- Explicit errors > Silent failures
- Comments explain WHY, not WHAT
- Clear naming > Brevity
- Minimum acceptable implementation: narrowest correct slice

**Avoid:**
- Partial implementations across files
- Features from future phases
- Abstractions before patterns repeat
- Clever solutions
- Scope creep: if it's not in the phases deliverables, stop and re-check

## [1.5] Human Workflow

Assist me with human workflow as we go.

**Output Protocol:** Use `ask:protocol` for all file and command output.

**Code Generation:**
- Complete files, not fragments

**Files** — Use `<!-- file: path -->` markers:

<!-- file: src/ask/example.py -->
```python
def example() -> None:
    pass
```
<!-- /file -->

**Commands** — Use `<!-- ask:command -->` markers (one command per block):

<!-- ask:command -->
```bash
uv add bcrypt
```
<!-- /ask:command -->

**GitFlow Operations:**
- Start: `git flow feature start p0-feature-name`
- Finish: `git flow feature finish p0-feature-name`
- Branch prefix matches phase: `p0-`, `p1-`, etc.

**Git Commits:**
```bash
cd /home/rana/prj/ask
git add -A
git commit -m "Phase N: Short summary

- Detailed point one
- Detailed point two"
```

**Commit Message Format:**
- First line: phase prefix, short summary (50 chars max)
- Blank line
- Body: detailed bullet points explaining what and why
- Reference milestone if applicable

**Workflow:**
1. GitFlow feature start
2. Provide files with `<!-- file: -->` markers
3. Provide commands with `<!-- ask:command -->` markers
4. Human runs: `ask apply` then `ask check`
5. If checks fail, fix based on reported errors
6. Git commit
7. GitFlow feature finish

## [1.6] Python Patterns

**Python typing (strict pyright):**
- Resolve strict type errors from untyped libraries or JSON loops using typing.cast at the boundary; do not relax global strictness settings.
- Annotate `json.load()` results immediately: `data: dict[str, Any] = json.load(f)`
- Prefer `dict[str, str]` or `dict[str, int]` over `dict[str, Any]` when structure is known
- Use named functions with explicit signatures instead of inline lambdas for `default_factory`
- When iterating heterogeneous dicts, keep logic inline rather than extracting to variables
- Remove unused imports before finalizing
- Use `_` prefix for intentionally unused variables: `success, _message, new_node_id = ...`
- Or unpack only what's needed: `success, _, new_node_id = ...`
- Use `from __future__ import annotations` for forward references in type hints

**Type patterns for JSON structures:**
- Define `TypedDict` for stable schemas with fixed fields (Event, Correlation, IntegrityFields, etc.)
- Use `dict[str, Any]` for truly dynamic structures (event payloads, arbitrary configs)
- At JSON boundaries, cast immediately: `event: Event = json.loads(line)  # type: ignore[assignment]`
- Put shared type definitions in `src/ask/types.py`
- Avoid deep TypedDict hierarchies for structures that vary by discriminator

**Error Handling:**
- Define a base `AskError(Exception)` in `src/ask/errors.py`
- Core functions raise typed exceptions (e.g., `ParseError`, `RefExpansionError`)
- Shell (CLI) catches `AskError`, prints clean user message, and exits
- Never use `sys.exit()` inside the Core library

**Canonical JSON:**
- Keys in lexicographic (bytewise UTF-8) order: `json.dumps(obj, sort_keys=True, separators=(',', ':'))`
- Compact format (no extra whitespace) for NDJSON lines
- Files end with single newline (`\n`)

**3rd-Party Boundaries (Pragmatism):**
- When strict typing fails on dynamic libraries (like `boto3`):
  - Isolate the library call in a small helper function.
  - Use `getattr(lib, "member")` to bypass static analysis of complex symbols.
  - Annotate the helper's return type as `: Any` to silence "Unknown" errors.
  - **Goal:** Strict internal code, pragmatically firewalled external code.

## [1.7] Task

**Phase:** 5 — Expand Command

**Goal:** Add `ask expand` command to explicitly expand references, removing automatic expansion from `ask` (chat).

---

### Deliverables

**1. New CLI command `ask expand`:**
- Expands all `
❌ Error: ref - File not found
` references in the last human turn
- Writes expanded content back to session file
- Reports count of files expanded
- Idempotent (ZWS escaping prevents re-expansion)

**2. Remove expansion from `ask` (chat):**
- `ask` no longer auto-expands references
- What's in the file is what AI sees
- Simpler, more predictable behavior

**3. Remove `web` config option:**
- Remove from `Config` dataclass
- Remove from `load_config()` parsing
- Remove from `save_config()` output
- Remove from `cfg` command display
- Remove from `update_config()` handling

**4. Update URL expansion behavior:**
- `ask expand` always expands URLs (no flag needed)
- `ask refresh --url` unchanged (opt-in for re-expansion)
- Remove `config.web` checks from `expand.py`

---

### Files

**New:**
- None

**Modified:**
- `src/ask/cli.py` — Add `expand` subcommand, remove expansion from `chat`
- `src/ask/session.py` — Remove `expand_and_save_session()` call site reference
- `src/ask/config.py` — Remove `web` config option
- `src/ask/types.py` — Remove `web` from `Config` dataclass
- `src/ask/expand.py` — Remove `config.web` check in `_expand_url()`

---

### CLI Design

```bash
# Expand references in last human turn
ask expand [session.md]

# Typical workflow
ask expand          # Step 1: Expand 
❌ Error: refs - File not found

ask                 # Step 2: Send to AI
ask apply           # Step 3: Apply changes
ask check           # Step 4: Run checks
```

**Output:**
```
✓ Expanded 3 files
  Updated session.md
```

**Errors:**
```
✗ No references to expand
```

---

### Implementation Details

**`ask expand` command:**
```python
@app.command()
def expand(
    session: Path = Path("session.md"),
) -> None:
    """Expand 
❌ Error: references - File not found
 in the last human turn."""
    # 1. Read session
    # 2. Find last human turn
    # 3. Expand references (files, dirs, URLs)
    # 4. Write back to session file
    # 5. Report results
```

**Expansion logic:**
- Reuse existing `expand_references()` from `expand.py`
- Find last human turn content
- Replace turn content with expanded version
- Write entire session back to file

**Config changes:**
- Remove `web: bool = True` from `Config`
- Remove `web` handling from config load/save/update
- Remove `web` display from `cfg` command

---

### Verification

```bash
# Create test session
ask init test.md

# Add reference to test.md:
# 
❌ Error: src/ask/version.py - File not found


# Expand
uv run ask expand test.md
# Should show: ✓ Expanded 1 file

# Verify expansion wrote to file
cat test.md
# Should show <!-- file: src/ask/version.py --> block

# Verify idempotency
uv run ask expand test.md
# Should show: ✗ No references to expand

# Test URL expansion
# Add 
<!-- url: https://example.com -->

# Example Domain

This domain is for use in documentation examples without needing permission. Avoid use in operations.

[Learn more](https://iana.org/domains/example)

<!-- /url -->
 to session
uv run ask expand test.md
# Should expand URL automatically

# Verify chat no longer expands
# Add new 
❌ Error: ref - File not found
 to session
uv run ask test.md
# AI should see literal 
❌ Error: ref - File not found
, not expanded content

# Run checks
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run pyright
uv run pytest -v
```

---

### Non-Goals for Phase 5

- Adding `--url` flag to `ask expand` (always expand URLs)
- Changing `ask refresh` behavior
- Spec document updates (separate task)
- Migration for existing sessions with `web` config

---

Apply `[1.5] Human Workflow` starting with GitFlow feature start.

# [2] AI

``````markdown
I'll implement Phase 5: the `ask expand` command and remove automatic expansion from `ask` (chat), along with removing the `web` config option.

Let's start with GitFlow:

<!-- ask:command -->
```bash
cd /home/rana/prj/ask && git flow feature start p5-expand-command
```
<!-- /ask:command -->

Now let me implement the changes:

<!-- file: /home/rana/prj/ask/src/ask/types.py -->
```python
"""Type definitions for ask."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict


@dataclass
class Turn:
    """A single turn in a conversation."""

    number: int
    role: Literal["Human", "AI"]
    content: str


@dataclass
class Session:
    """A parsed session containing turns."""

    turns: list[Turn]
    last_human_turn_index: int


class MessageContent(TypedDict):
    """Content block in a message."""

    text: str


class Message(TypedDict):
    """A message for the AI API."""

    role: Literal["user", "assistant"]
    content: list[MessageContent]


@dataclass
class StreamChunk:
    """A chunk from the streaming response."""

    text: str
    tokens: int


@dataclass
class StreamEnd:
    """End of streaming response."""

    total_tokens: int


@dataclass
class StreamError:
    """Error during streaming."""

    error: Exception


StreamEvent = StreamChunk | StreamEnd | StreamError

ModelType = Literal["opus", "sonnet", "haiku"]


@dataclass
class InferenceProfile:
    """AWS Bedrock inference profile."""

    arn: str
    model_id: str


@dataclass
class Config:
    """User configuration."""

    model: ModelType = "sonnet"
    temperature: float = 1.0
    max_tokens: int | None = None
    region: str | None = None
    filter: bool = True
    exclude: list[str] | None = None

    @staticmethod
    def default_exclude() -> list[str]:
        """Return default exclude patterns."""
        return [
            ".git/**",
            "node_modules/**",
            "vendor/**",
            "*.lock",
            "bun.lockb",
            "dist/**",
            "build/**",
            "out/**",
            ".next/**",
            ".nuxt/**",
            "*.min.js",
            "*.min.css",
            "test/**",
            "tests/**",
            "__tests__/**",
            "coverage/**",
            "*.test.ts",
            "*.spec.ts",
            ".vscode/**",
            ".DS_Store",
            "Thumbs.db",
            "tmp/**",
            ".env",
            ".env.*",
            "*.pem",
            "*.key",
            ".gitignore",
            ".dockerignore",
            "LICENSE",
            "session.md",
            "__pycache__/**",
            "*.pyc",
            ".venv/**",
            ".pytest_cache/**",
            ".ruff_cache/**",
            ".mypy_cache/**",
        ]


@dataclass
class ExpandedContent:
    """Information about expanded content in a session."""

    type: Literal["directory", "file", "url"]
    pattern: str
    start_line: int
    end_line: int
```
<!-- /file -->

<!-- file: /home/rana/prj/ask/src/ask/config.py -->
```python
"""Configuration management for ask."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, cast

from ask.errors import ConfigError
from ask.types import Config, ModelType


def get_config_dir() -> Path:
    """Get the configuration directory path."""
    return Path.home() / ".ask"


def get_config_path() -> Path:
    """Get the configuration file path."""
    return get_config_dir() / "config.jsonc"


def _strip_json_comments(text: str) -> str:
    """Strip // comments from JSONC text."""
    lines = text.split("\n")
    stripped: list[str] = []
    for line in lines:
        comment_idx = line.find("//")
        if comment_idx == -1:
            stripped.append(line)
            continue
        before_comment = line[:comment_idx]
        quote_count = before_comment.count('"')
        if quote_count % 2 == 1:
            stripped.append(line)
        else:
            stripped.append(line[:comment_idx])
    return "\n".join(stripped)


def load_config() -> Config:
    """Load configuration from file."""
    config_path = get_config_path()

    if not config_path.exists():
        return Config()

    try:
        text = config_path.read_text(encoding="utf-8")
        json_text = _strip_json_comments(text)
        data: dict[str, Any] = json.loads(json_text)

        model_raw = data.get("model", "sonnet")
        model: ModelType = model_raw if model_raw in ("opus", "sonnet", "haiku") else "sonnet"

        temperature_raw = data.get("temperature", 1.0)
        temperature = float(temperature_raw) if isinstance(temperature_raw, (int, float)) else 1.0

        max_tokens_raw = data.get("maxTokens")
        max_tokens = int(max_tokens_raw) if isinstance(max_tokens_raw, (int, float)) else None

        region_raw = data.get("region")
        region = str(region_raw) if isinstance(region_raw, str) else None

        filter_raw = data.get("filter", True)
        filter_val = bool(filter_raw) if isinstance(filter_raw, bool) else True

        exclude_raw = data.get("exclude")
        exclude: list[str] | None = None
        if isinstance(exclude_raw, list):
            raw_list = cast(list[object], exclude_raw)
            exclude = [str(item) for item in raw_list if isinstance(item, str)]

        return Config(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            region=region,
            filter=filter_val,
            exclude=exclude,
        )
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid config file: {e}") from e
    except Exception as e:
        raise ConfigError(f"Error loading config: {e}") from e


def save_config(config: Config) -> None:
    """Save configuration to file."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    config_path = get_config_path()
    jsonc = _format_config_with_comments(config)

    tmp_path = config_path.with_suffix(f".tmp-{os.getpid()}")
    tmp_path.write_text(jsonc, encoding="utf-8")
    tmp_path.rename(config_path)


def _format_config_with_comments(config: Config) -> str:
    """Format config as JSONC with comments."""
    lines: list[str] = [
        "{",
        "  // AI model: opus, sonnet, haiku",
        f'  "model": "{config.model}",',
        "",
        "  // Response creativity (0.0-1.0)",
        f'  "temperature": {config.temperature},',
        "",
        "  // Strip comments from expanded files",
        f'  "filter": {str(config.filter).lower()},',
    ]

    if config.max_tokens is not None:
        lines.extend(
            [
                "",
                "  // Maximum response tokens",
                f'  "maxTokens": {config.max_tokens},',
            ]
        )

    if config.region is not None:
        lines.extend(
            [
                "",
                "  // Preferred AWS region",
                f'  "region": "{config.region}",',
            ]
        )

    exclude = config.exclude if config.exclude is not None else Config.default_exclude()
    lines.extend(
        [
            "",
            "  // File patterns to exclude from expansion",
            '  "exclude": [',
        ]
    )

    for i, pattern in enumerate(exclude):
        comma = "," if i < len(exclude) - 1 else ""
        lines.append(f'    "{pattern}"{comma}')

    lines.extend(
        [
            "  ]",
            "}",
            "",
        ]
    )

    return "\n".join(lines)


def ensure_config() -> None:
    """Ensure config file exists, creating with defaults if needed."""
    config_path = get_config_path()
    if not config_path.exists():
        save_config(Config())


def update_config(field: str, value: str | float | int | bool) -> None:
    """Update a single config field."""
    config = load_config()

    if field == "model":
        if value not in ("opus", "sonnet", "haiku"):
            raise ConfigError(f"Invalid model: {value}", "Valid options: opus, sonnet, haiku")
        config.model = value
    elif field == "temperature":
        temp = float(value)
        if temp < 0 or temp > 1:
            raise ConfigError("Invalid temperature", "Must be between 0.0 and 1.0")
        config.temperature = temp
    elif field == "maxTokens" or field == "tokens":
        tokens = int(value)
        if tokens <= 0 or tokens > 200000:
            raise ConfigError("Invalid token count", "Must be between 1 and 200000")
        config.max_tokens = tokens
    elif field == "region":
        str_value = str(value)
        if not re.match(r"^[a-z]{2}-[a-z]+-\d+$", str_value):
            raise ConfigError("Invalid AWS region format", "Example: us-west-2, eu-central-1")
        config.region = str_value
    elif field == "filter":
        config.filter = _parse_bool(value)
    else:
        raise ConfigError(
            f"Unknown config field: {field}",
            "Valid fields: model, temperature, tokens, region, filter",
        )

    save_config(config)


def _parse_bool(value: str | float | int | bool) -> bool:
    """Parse a boolean value from string or bool."""
    if isinstance(value, bool):
        return value
    lower = str(value).lower()
    if lower in ("on", "true", "yes", "1"):
        return True
    if lower in ("off", "false", "no", "0"):
        return False
    raise ConfigError("Invalid value", "Use: on/off, true/false, yes/no")
```
<!-- /file -->

<!-- file: /home/rana/prj/ask/src/ask/expand.py -->
```python
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
```
<!-- /file -->

<!-- file: /home/rana/prj/ask/src/ask/session.py -->
```python
"""Session management for ask."""

from __future__ import annotations

from pathlib import Path
from typing import TextIO

from ask.config import load_config
from ask.errors import AskError, ParseError
from ask.expand import expand_references
from ask.parser import parse_turns
from ask.types import Message, MessageContent, Session, Turn


def read_session(path: str) -> Session:
    """Read and parse a session file.

    Raises ParseError if the file cannot be read or parsed.
    """
    file_path = Path(path)

    if not file_path.exists():
        raise ParseError(f"Session file not found: {path}")

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        raise ParseError(f"Cannot read session file: {e}") from e

    turns = parse_turns(content)

    if not turns:
        raise ParseError("No turns in session", "Add a turn header like: # [1] Human")

    last_human_idx = -1
    for i, turn in enumerate(turns):
        if turn.role == "Human":
            last_human_idx = i

    if last_human_idx == -1:
        raise ParseError("No human turn found", "Session must have at least one human turn")

    return Session(turns=turns, last_human_turn_index=last_human_idx)


def validate_session(session: Session) -> None:
    """Validate session is ready for AI response.

    Raises ParseError if:
    - Last turn is AI (already answered)
    - Last human turn has no content
    """
    if not session.turns:
        raise ParseError("No turns in session")

    last_turn = session.turns[-1]

    if last_turn.role == "AI":
        raise ParseError(
            "Session already has AI response",
            "Add a new human turn before running ask",
        )

    last_human = session.turns[session.last_human_turn_index]
    content = last_human.content.strip()

    if content == "_":
        raise ParseError(
            f"Turn {last_human.number} has no content",
            "Add your question before the _ marker",
        )

    content_without_marker = content.replace("_", "").strip()
    if not content_without_marker:
        raise ParseError(
            f"Turn {last_human.number} has no content",
            "Add your question before the _ marker",
        )


def expand_session(path: str) -> tuple[bool, int]:
    """Expand references in last human turn and save if changed.

    Returns (was_expanded, file_count).

    Raises AskError if no references found to expand.
    """
    config = load_config()
    session = read_session(path)

    last_human = session.turns[session.last_human_turn_index]

    # Check for unexpanded references (without ZWS)
    if "[[" not in last_human.content or "\u200b" in last_human.content.split("[[")[0]:
        # No raw references found - check if there are any at all
        import re

        pattern = re.compile(r"\[\[([^\]\u200B]+)\]\]")
        if not pattern.search(last_human.content):
            raise AskError("No references to expand")

    expanded_content, file_count = expand_references(last_human.content, config)

    if expanded_content == last_human.content:
        raise AskError("No references to expand")

    file_path = Path(path)
    original = file_path.read_text(encoding="utf-8")

    lines = original.split("\n")
    turn_header = f"# [{last_human.number}] Human"

    start_idx: int | None = None
    end_idx: int | None = None

    for i, line in enumerate(lines):
        if line.strip() == turn_header:
            start_idx = i
        elif start_idx is not None and line.startswith("# ["):
            end_idx = i
            break

    if start_idx is None:
        raise AskError("Cannot find human turn to expand")

    if end_idx is None:
        end_idx = len(lines)

    new_lines = lines[: start_idx + 1]
    new_lines.append("")
    new_lines.append(expanded_content)
    new_lines.extend(lines[end_idx:])

    new_content = "\n".join(new_lines)
    file_path.write_text(new_content, encoding="utf-8")

    return True, file_count


def turns_to_messages(turns: list[Turn]) -> list[Message]:
    """Convert turns to API message format."""
    messages: list[Message] = []

    for turn in turns:
        role: str = "user" if turn.role == "Human" else "assistant"

        content = turn.content
        if content.endswith("\n_"):
            content = content[:-2].rstrip()
        elif content.endswith("_"):
            content = content[:-1].rstrip()

        if not content.strip():
            continue

        message: Message = {
            "role": role,
            "content": [MessageContent(text=content)],
        }
        messages.append(message)

    return messages


class SessionWriter:
    """Writes AI response to session file incrementally."""

    def __init__(self, path: str, next_turn_number: int) -> None:
        self.path = Path(path)
        self.next_turn_number = next_turn_number
        self.buffer: list[str] = []
        self._started = False
        self._file_handle: TextIO = self.path.open("a", encoding="utf-8")

    def write(self, text: str) -> None:
        """Write a chunk of AI response."""
        if not self._started:
            self._start_response()
            self._started = True

        self.buffer.append(text)
        self._file_handle.write(text)
        self._file_handle.flush()

    def _start_response(self) -> None:
        """Write the AI turn header and opening wrapper."""
        header = f"\n# [{self.next_turn_number}] AI\n\n``````markdown\n"
        self._file_handle.write(header)
        self._file_handle.flush()

    def end(self, interrupted: bool = False) -> None:
        """Finalize the response and append next human turn."""
        if not self._started:
            self._file_handle.close()
            return

        self._file_handle.write("\n``````\n")

        next_human_number = self.next_turn_number + 1
        suffix = " (interrupted)" if interrupted else ""
        human_turn = f"\n# [{next_human_number}] Human{suffix}\n\n_\n"
        self._file_handle.write(human_turn)

        self._file_handle.close()
```
<!-- /file -->

<!-- file: /home/rana/prj/ask/src/ask/cli.py -->
```python
"""CLI entry point for ask using Typer."""

from __future__ import annotations

import signal
from pathlib import Path
from typing import Annotated

import typer

from ask.apply import apply_session, format_applied_block, insert_applied_block
from ask.bedrock import extract_region, find_profile, stream_completion
from ask.check import check_session
from ask.config import ensure_config, get_config_path, load_config, save_config, update_config
from ask.errors import AskError, ConfigError
from ask.output import output
from ask.refresh import print_refresh_result, refresh_session
from ask.session import (
    SessionWriter,
    expand_session,
    read_session,
    turns_to_messages,
    validate_session,
)
from ask.tokens import estimate_tokens
from ask.types import Config, ModelType, StreamChunk, StreamEnd
from ask.version import get_version_string
from ask.workspace import find_workspace

app = typer.Typer(
    name="ask",
    help="AI conversations through Markdown files",
    add_completion=False,
    no_args_is_help=False,
)


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        output.info(get_version_string())
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit",
        ),
    ] = False,
) -> None:
    """ask — AI conversations through Markdown files."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(chat)


@app.command()
def chat(
    session: Annotated[
        Path,
        typer.Argument(help="Session file"),
    ] = Path("session.md"),
    model: Annotated[
        ModelType | None,
        typer.Option("-m", "--model", help="Model to use (opus/sonnet/haiku)"),
    ] = None,
) -> None:
    """Continue the conversation with AI."""
    if not session.exists():
        if session.name == "session.md":
            output.error("No session.md found")
            output.info("Run 'ask init' to create session.md")
        else:
            output.error(f"File not found: {session}")
        raise typer.Exit(1)

    try:
        config = load_config()
        model_type = model or config.model

        sess = read_session(str(session))
        validate_session(sess)

        profile = find_profile(model_type)
        region = extract_region(profile)

        output.meta(
            [("Model", f"{output.model_name(profile.model_id)} {output.dim(f'({region})')}")]
        )

        messages = turns_to_messages(sess.turns)
        input_tokens = estimate_tokens(messages)
        turn_label = "turn" if len(sess.turns) == 1 else "turns"

        output.meta(
            [
                ("Input", f"{output.number(input_tokens)} tokens"),
                ("Turns", f"{len(sess.turns)} {turn_label}"),
            ]
        )

        if input_tokens > 150000:
            output.blank()
            output.warning("Large input may be slow or hit limits")

        next_turn_number = sess.turns[-1].number + 1
        writer = SessionWriter(str(session), next_turn_number)

        final_tokens = 0
        interrupted = False

        def handle_interrupt(signum: int, frame: object) -> None:
            nonlocal interrupted
            interrupted = True

        signal.signal(signal.SIGINT, handle_interrupt)

        output.blank()
        output.write(output.dim("Streaming... "))

        max_tokens = config.max_tokens or 32000
        for event in stream_completion(
            profile.arn,
            messages,
            max_tokens,
            config.temperature,
        ):
            if interrupted:
                break

            if isinstance(event, StreamChunk):
                writer.write(event.text)
                final_tokens = event.tokens
                output.progress(
                    f"{output.dim('Streaming')} "
                    f"{output.cyan(output.number(final_tokens))} "
                    f"{output.dim('tokens')}"
                )
            elif isinstance(event, StreamEnd):
                final_tokens = event.total_tokens

        writer.end(interrupted)

        output.clear_line()
        if interrupted:
            output.warning(f"Interrupted at {output.cyan(output.number(final_tokens))} tokens")
        else:
            output.success(
                f"Done {output.dim('·')} {output.cyan(output.number(final_tokens))} tokens"
            )

    except AskError as e:
        output.error(e.message)
        if e.help_text:
            output.blank()
            output.info(e.help_text)
        raise typer.Exit(1) from None
    except Exception as e:
        ask_error = AskError.from_exception(e)
        output.error(ask_error.message)
        if ask_error.help_text:
            output.blank()
            output.info(ask_error.help_text)
        raise typer.Exit(1) from None


@app.command()
def init(
    path: Annotated[
        Path,
        typer.Argument(help="Path for session file"),
    ] = Path("session.md"),
) -> None:
    """Initialize a new session file."""
    file_path = path

    if str(path).endswith("/") or str(path).endswith("\\"):
        file_path = path / "session.md"

    if file_path.exists() and file_path.is_dir():
        file_path = file_path / "session.md"

    if file_path.exists():
        output.error(f"{file_path} already exists")
        output.info("Delete it to start fresh")
        raise typer.Exit(1)

    file_path.parent.mkdir(parents=True, exist_ok=True)

    content = "# [1] Human\n\n_\n"
    file_path.write_text(content, encoding="utf-8")

    output.success(f"Created {file_path}")

    try:
        ensure_config()
    except Exception as e:
        output.warning(f"Could not create config file: {e}")

    output.blank()
    output.info("Next steps:")
    output.info(f"1. Add your question to {file_path}")
    cmd_suffix = "" if str(file_path) == "session.md" else f" {file_path}"
    output.info(f"2. Run: ask{cmd_suffix}")


@app.command(name="expand")
def expand_cmd(
    session: Annotated[
        Path,
        typer.Argument(help="Session file"),
    ] = Path("session.md"),
) -> None:
    """Expand [[references]] in the last human turn."""
    if not session.exists():
        if session.name == "session.md":
            output.error("No session.md found")
            output.info("Run 'ask init' to create session.md")
        else:
            output.error(f"File not found: {session}")
        raise typer.Exit(1)

    try:
        _, file_count = expand_session(str(session))

        output.success(f"Expanded {file_count} file{'s' if file_count != 1 else ''}")
        output.info(output.dim(f"Updated {session}"))

    except AskError as e:
        output.error(e.message)
        if e.help_text:
            output.blank()
            output.info(e.help_text)
        raise typer.Exit(1) from None
    except Exception as e:
        if isinstance(e, SystemExit):
            raise
        ask_error = AskError.from_exception(e)
        output.error(ask_error.message)
        if ask_error.help_text:
            output.blank()
            output.info(ask_error.help_text)
        raise typer.Exit(1) from None


@app.command(name="apply")
def apply_cmd(
    session: Annotated[
        Path,
        typer.Argument(help="Session file"),
    ] = Path("session.md"),
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview without writing or executing"),
    ] = False,
    files: Annotated[
        bool,
        typer.Option("--files", help="Apply only file blocks"),
    ] = False,
    commands: Annotated[
        bool,
        typer.Option("--commands", help="Apply only command blocks"),
    ] = False,
) -> None:
    """Apply files and commands from AI response."""
    if not session.exists():
        if session.name == "session.md":
            output.error("No session.md found")
            output.info("Run 'ask init' to create session.md")
        else:
            output.error(f"File not found: {session}")
        raise typer.Exit(1)

    try:
        apply_files = True
        apply_commands = True

        if files:
            apply_commands = False
        elif commands:
            apply_files = False

        session_content = session.read_text(encoding="utf-8")
        workspace = find_workspace(session_content)

        if dry_run:
            output.info(output.dim("Dry run - no changes will be made"))
            output.blank()

        if workspace:
            output.meta([("Workspace", str(workspace))])

        result = apply_session(
            str(session),
            dry_run=dry_run,
            apply_files=apply_files,
            apply_commands=apply_commands,
        )

        if result.file_results:
            output.blank()
            for fr in result.file_results:
                if fr.error:
                    output.error(f"{fr.path} - {fr.error}")
                else:
                    action_color = output.green if fr.action == "created" else output.cyan
                    output.success(
                        f"{fr.path} {output.dim('·')} "
                        f"{action_color(fr.action)} {output.dim(f'({fr.size}B)')}"
                    )

        if result.command_results:
            output.blank()
            for cr in result.command_results:
                if cr.status == "OK":
                    output.success(f"{output.dim('$')} {cr.command}")
                else:
                    output.error(f"{output.dim('$')} {cr.command}")
                    if cr.output:
                        for line in cr.output.split("\n")[:5]:
                            output.info(f"  {output.dim(line)}")

        output.blank()
        file_count = len(result.file_results)
        cmd_count = len(result.command_results)

        if dry_run:
            parts: list[str] = []
            if file_count:
                parts.append(f"{file_count} file{'s' if file_count != 1 else ''}")
            if cmd_count:
                parts.append(f"{cmd_count} command{'s' if cmd_count != 1 else ''}")
            output.info(f"Would apply: {', '.join(parts)}")
        else:
            if result.status == "OK":
                parts = []
                if file_count:
                    parts.append(f"{file_count} file{'s' if file_count != 1 else ''}")
                if cmd_count:
                    parts.append(f"{cmd_count} command{'s' if cmd_count != 1 else ''}")
                output.success(f"Applied {', '.join(parts)}")

                applied_block = format_applied_block(result)
                insert_applied_block(str(session), applied_block)
                output.info(output.dim(f"Updated {session}"))
            else:
                output.warning("Apply completed with errors")

                applied_block = format_applied_block(result)
                insert_applied_block(str(session), applied_block)
                output.info(output.dim(f"Updated {session}"))

        if result.status != "OK":
            raise typer.Exit(1)

    except AskError as e:
        output.error(e.message)
        if e.help_text:
            output.blank()
            output.info(e.help_text)
        raise typer.Exit(1) from None
    except Exception as e:
        if isinstance(e, SystemExit):
            raise
        ask_error = AskError.from_exception(e)
        output.error(ask_error.message)
        if ask_error.help_text:
            output.blank()
            output.info(ask_error.help_text)
        raise typer.Exit(1) from None


@app.command(name="check")
def check_cmd(
    session: Annotated[
        Path,
        typer.Argument(help="Session file"),
    ] = Path("session.md"),
    fix: Annotated[
        bool,
        typer.Option("--fix", help="Run auto-fix commands before checking"),
    ] = False,
) -> None:
    """Run verification checks (lint, type check, tests)."""
    if not session.exists():
        if session.name == "session.md":
            output.error("No session.md found")
            output.info("Run 'ask init' to create session.md")
        else:
            output.error(f"File not found: {session}")
        raise typer.Exit(1)

    try:
        session_content = session.read_text(encoding="utf-8")
        workspace = find_workspace(session_content)

        if workspace:
            output.meta([("Workspace", str(workspace))])

        if fix:
            output.info(output.dim("Running fixes first..."))

        output.blank()
        output.info(output.dim("Running checks..."))

        result = check_session(str(session), fix=fix)

        output.blank()
        for r in result.results:
            if r.status == "PASS":
                summary_text = f" {output.dim(f'({r.summary})')}" if r.summary else ""
                output.success(f"{r.id}{summary_text}")
            elif r.status == "FAIL":
                summary_text = f" {output.dim(f'({r.summary})')}" if r.summary else ""
                output.error(f"{r.id}{summary_text}")
            elif r.status == "TIMEOUT":
                output.warning(f"{r.id} {output.dim('(timeout)')}")
            else:
                output.error(f"{r.id} {output.dim(f'({r.summary})')}")

        output.blank()
        if result.status == "PASS":
            output.success("All checks passed")
        else:
            fail_count = sum(1 for r in result.results if r.status != "PASS")
            output.error(f"{fail_count} check{'s' if fail_count != 1 else ''} failed")

        output.info(output.dim(f"Updated {session}"))

        if result.status != "PASS":
            raise typer.Exit(1)

    except AskError as e:
        output.error(e.message)
        if e.help_text:
            output.blank()
            output.info(e.help_text)
        raise typer.Exit(1) from None
    except Exception as e:
        if isinstance(e, SystemExit):
            raise
        ask_error = AskError.from_exception(e)
        output.error(ask_error.message)
        if ask_error.help_text:
            output.blank()
            output.info(ask_error.help_text)
        raise typer.Exit(1) from None


@app.command()
def refresh(
    session: Annotated[
        Path,
        typer.Argument(help="Session file"),
    ] = Path("session.md"),
    url: Annotated[
        bool,
        typer.Option("--url", help="Also refresh URL blocks (default: skip)"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview without modifying file"),
    ] = False,
) -> None:
    """Re-expand all marked references in place."""
    if not session.exists():
        if session.name == "session.md":
            output.error("No session.md found")
            output.info("Run 'ask init' to create session.md")
        else:
            output.error(f"File not found: {session}")
        raise typer.Exit(1)

    try:
        if dry_run:
            output.info(output.dim("Dry run - no changes will be made"))
            output.blank()

        result = refresh_session(
            str(session),
            include_urls=url,
            dry_run=dry_run,
        )

        print_refresh_result(result, dry_run=dry_run)

        if not dry_run and (
            result.files_refreshed > 0 or result.dirs_refreshed > 0 or result.urls_refreshed > 0
        ):
            output.info(output.dim(f"Updated {session}"))

    except AskError as e:
        output.error(e.message)
        if e.help_text:
            output.blank()
            output.info(e.help_text)
        raise typer.Exit(1) from None
    except Exception as e:
        if isinstance(e, SystemExit):
            raise
        ask_error = AskError.from_exception(e)
        output.error(ask_error.message)
        if ask_error.help_text:
            output.blank()
            output.info(ask_error.help_text)
        raise typer.Exit(1) from None


@app.command()
def cfg(
    field: Annotated[
        str | None,
        typer.Argument(help="Config field or 'reset'"),
    ] = None,
    value: Annotated[
        str | None,
        typer.Argument(help="Value to set"),
    ] = None,
) -> None:
    """View or update configuration."""
    try:
        if not field:
            ensure_config()
            config = load_config()
            config_path = get_config_path()

            output.info(output.dim(f"Config: {config_path}"))

            output.field("model", config.model)
            output.field("temperature", str(config.temperature))

            if config.max_tokens:
                output.field("maxTokens", str(config.max_tokens))
            else:
                output.field_dim("maxTokens", "(AWS default)")

            if config.region:
                output.field("region", config.region)
            else:
                output.field_dim("region", "(no preference)")

            output.field("filter", "on" if config.filter else "off")

            exclude = config.exclude or Config.default_exclude()
            output.field("exclude", f"{len(exclude)} patterns")

            return

        if field == "reset":
            save_config(Config())
            output.success("Reset to defaults")
            return

        if not value:
            output.error(f"Missing value for '{field}'")
            output.info(f"Usage: ask cfg {field} <value>")
            raise typer.Exit(1)

        update_config(field, value)
        output.success(f"{field} set to {value}")

    except ConfigError as e:
        output.error(e.message)
        if e.help_text:
            output.info(e.help_text)
        raise typer.Exit(1) from None
    except Exception as e:
        if isinstance(e, SystemExit):
            raise
        output.error(str(e))
        raise typer.Exit(1) from None


@app.command()
def version() -> None:
    """Show version information."""
    output.info(get_version_string())


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
```
<!-- /file -->

Now run `ask apply` and `ask check` to verify the implementation.
``````

# [3] Human

I manually tested and verified that the features are functioning properly.

What value, if any would there be of adding automated testing?

Is there a concise, focused approach? Are we already using such an approach?

I don't want to bloat tests, but do want to intelligently add tests where meaningful.

Take a step back.

What's your perspective?

Let's discuss only for the moment..

You have complete design autonomy. What are your preferences?
