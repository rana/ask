"""AWS Bedrock client for AI interactions."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any, cast

import boto3
from botocore.config import Config as BotoConfig

from ask.config import load_config
from ask.errors import AskError
from ask.types import (
    InferenceProfile,
    Message,
    ModelType,
    StreamChunk,
    StreamEnd,
    StreamEvent,
)

TIMEOUT_SECONDS = 300  # 5 minutes


def _get_boto3_client(service: str, region: str | None = None) -> Any:
    """
    Get a raw boto3 client.
    
    We use getattr(boto3, "client") to bypass strict Pyright checks.
    Directly accessing 'boto3.client' triggers "Partially Unknown" errors 
    because the type definition contains a massive, complex Overload union.
    """
    config = BotoConfig(
        read_timeout=TIMEOUT_SECONDS,
        connect_timeout=30,
        retries={"max_attempts": 3, "mode": "adaptive"},
    )
    
    # Firewall: Dynamic access bypasses static analysis of the symbol
    client_factory: Any = getattr(boto3, "client")
    
    return client_factory(
        service,
        region_name=region or "us-west-2",
        config=config,
    )


def find_profile(model_type: ModelType) -> InferenceProfile:
    """Find an inference profile for the given model type."""
    config = load_config()
    region = config.region or "us-west-2"

    client = _get_boto3_client("bedrock", region)

    # List inference profiles
    all_profiles: list[dict[str, Any]] = []
    next_token: str | None = None

    while True:
        kwargs: dict[str, Any] = {"maxResults": 100}
        if next_token:
            kwargs["nextToken"] = next_token

        response = cast(dict[str, Any], client.list_inference_profiles(**kwargs))
        
        profiles = cast(
            list[dict[str, Any]], response.get("inferenceProfileSummaries", [])
        )
        all_profiles.extend(profiles)

        next_token = cast(str | None, response.get("nextToken"))
        if not next_token:
            break

    if not all_profiles:
        raise AskError(
            "No inference profiles found",
            "Check your AWS account has cross-region inference enabled",
        )

    # Find matching profiles
    matches: list[dict[str, Any]] = []

    for profile in all_profiles:
        arn = cast(str, profile.get("inferenceProfileArn", ""))
        models = cast(list[dict[str, Any]], profile.get("models", []))

        arn_region = _extract_region_from_arn(arn)

        for model in models:
            model_arn = cast(str, model.get("modelArn", ""))
            if model_type.lower() not in model_arn.lower():
                continue

            model_id = model_arn.split("/")[-1] if "/" in model_arn else model_arn
            version = _parse_model_version(model_id)

            matches.append({
                "arn": arn,
                "model_id": model_id,
                "version": version,
                "region": arn_region,
            })

    if not matches:
        raise AskError(
            f"No inference profile found for {model_type} models",
            "Check AWS Bedrock console for available models",
        )

    # Sort by preferred region, then version
    preferred_region = config.region

    def sort_key(m: dict[str, Any]) -> tuple[int, int, int, str]:
        region_priority = 0 if m["region"] == preferred_region else 1
        v = cast(dict[str, Any], m["version"])
        return (
            region_priority, 
            -cast(int, v["major"]), 
            -cast(int, v["minor"]), 
            cast(str, v["date"])
        )

    matches.sort(key=sort_key)

    selected = matches[0]
    return InferenceProfile(
        arn=cast(str, selected["arn"]),
        model_id=cast(str, selected["model_id"]),
    )


def _extract_region_from_arn(arn: str) -> str:
    """Extract AWS region from an ARN."""
    match = re.search(r"arn:aws:bedrock:([^:]+):", arn)
    return match.group(1) if match else "unknown"


def _parse_model_version(model_id: str) -> dict[str, Any]:
    """Parse version info from a model ID."""
    date_match = re.search(r"(\d{8})", model_id)
    date = date_match.group(1) if date_match else "00000000"

    parts = model_id.split("-")
    version_parts: list[int] = []

    for part in parts:
        if part.isdigit():
            version_parts.append(int(part))
        if part == date:
            break

    major = version_parts[0] if version_parts else 3
    minor = version_parts[1] if len(version_parts) > 1 else 0

    return {"major": major, "minor": minor, "date": date}


def stream_completion(
    profile_arn: str,
    messages: list[Message],
    max_tokens: int,
    temperature: float = 1.0,
) -> Iterator[StreamEvent]:
    """Stream a completion from Bedrock."""
    config = load_config()
    region = config.region or "us-west-2"

    client = _get_boto3_client("bedrock-runtime", region)

    effective_max_tokens = min(max_tokens, 64000)

    try:
        response = client.converse_stream(
            modelId=profile_arn,
            messages=messages,
            inferenceConfig={
                "temperature": temperature,
                "maxTokens": effective_max_tokens,
            },
        )

        total_tokens = 0

        stream = cast(list[dict[str, Any]], response.get("stream", []))

        for event in stream:
            if "contentBlockDelta" in event:
                delta = cast(dict[str, Any], event["contentBlockDelta"].get("delta", {}))
                text = cast(str, delta.get("text", ""))
                if text:
                    tokens = len(text) // 4 + 1
                    total_tokens += tokens
                    yield StreamChunk(text=text, tokens=total_tokens)

            if "metadata" in event:
                metadata = cast(dict[str, Any], event["metadata"])
                usage = cast(dict[str, Any], metadata.get("usage", {}))
                if "outputTokens" in usage:
                    total_tokens = cast(int, usage["outputTokens"])

        yield StreamEnd(total_tokens=total_tokens)

    except Exception as e:
        raise AskError.from_exception(e) from e


def extract_region(profile: InferenceProfile) -> str:
    """Extract region from an inference profile ARN."""
    return _extract_region_from_arn(profile.arn)