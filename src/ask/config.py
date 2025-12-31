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

        web_raw = data.get("web", True)
        web_val = bool(web_raw) if isinstance(web_raw, bool) else True

        exclude_raw = data.get("exclude")
        exclude: list[str] | None = None
        if isinstance(exclude_raw, list):
            # Cast the list to known type at boundary
            raw_list = cast(list[object], exclude_raw)
            exclude = [str(item) for item in raw_list if isinstance(item, str)]

        return Config(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            region=region,
            filter=filter_val,
            web=web_val,
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
        "",
        "  // Enable URL expansion",
        f'  "web": {str(config.web).lower()},',
    ]

    if config.max_tokens is not None:
        lines.extend([
            "",
            "  // Maximum response tokens",
            f'  "maxTokens": {config.max_tokens},',
        ])

    if config.region is not None:
        lines.extend([
            "",
            "  // Preferred AWS region",
            f'  "region": "{config.region}",',
        ])

    exclude = config.exclude if config.exclude is not None else Config.default_exclude()
    lines.extend([
        "",
        "  // File patterns to exclude from expansion",
        '  "exclude": [',
    ])

    for i, pattern in enumerate(exclude):
        comma = "," if i < len(exclude) - 1 else ""
        lines.append(f'    "{pattern}"{comma}')

    lines.extend([
        "  ]",
        "}",
        "",
    ])

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
    elif field == "web":
        config.web = _parse_bool(value)
    else:
        raise ConfigError(
            f"Unknown config field: {field}",
            "Valid fields: model, temperature, tokens, region, filter, web",
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