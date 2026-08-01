"""Playground API — interactive LLM provider comparison endpoint.

This module defines the FastAPI router and Pydantic models for the
playground comparison endpoint. The developer will implement the
actual routing logic; stubs here raise NotImplementedError to define
the expected interface.

Endpoints:
    POST /api/playground/compare — compare all 9 providers side-by-side
    GET  /health                — health check
"""

from __future__ import annotations

import ipaddress
import os
import re
import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ai_vibe_coding.llm_wrapper import (
    AnthropicProvider,
    DeepSeekProvider,
    LLMResponse,
    MiMoProvider,
    OpenAIProvider,
    OpenRouterProvider,
)
from ai_vibe_coding.provider_examples import (
    CohereProvider,
    GeminiProvider,
    MistralProvider,
    OllamaProvider,
)

# ──────────────────────────────────────────────────────────────
# Request / Response models
# ──────────────────────────────────────────────────────────────

MAX_PROMPT_LENGTH = 20_000


class ProviderLatency(BaseModel):
    """Latency metrics for a single provider call."""

    time_to_first_token_ms: float = Field(
        default=0.0,
        description="Milliseconds until the first token of the response arrived",
    )
    total_ms: float = Field(
        default=0.0,
        description="Total response time in milliseconds",
    )


class PlaygroundProviderResult(BaseModel):
    """Result for a single provider in the playground comparison."""

    content: str = Field(default="", description="The generated text response")
    provider: str = Field(default="", description="Provider name (e.g. 'openai')")
    model: str = Field(default="", description="Model used (e.g. 'gpt-4')")
    tokens_used: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    latency: ProviderLatency = Field(default_factory=ProviderLatency)
    character_count: int = Field(default=0, ge=0)
    response_highlights: dict[str, Any] = Field(
        default_factory=dict,
        description="Structure highlights: code blocks, lists, tables, JSON, etc.",
    )
    error: str | None = Field(
        default=None,
        description="Error message if this provider call failed",
    )
    error_code: str | None = Field(
        default=None,
        description="Stable, user-facing error category",
    )
    recovery_action: str | None = Field(
        default=None,
        description="Safe next action for recovering from the error",
    )


class PlaygroundCompareRequest(BaseModel):
    """Request body for POST /api/playground/compare."""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=MAX_PROMPT_LENGTH,
        description="The user prompt to send to providers",
    )
    providers: list[str] | None = Field(
        default=None,
        description="List of providers to compare (default: all 9)",
    )
    system_prompt: str | None = Field(
        default=None,
        description="Optional system prompt prepended to the request",
    )


class PlaygroundCompareResponse(BaseModel):
    """Response body for POST /api/playground/compare."""

    results: dict[str, PlaygroundProviderResult] = Field(
        default_factory=dict,
        description="Provider name → result mapping",
    )
    total_latency_ms: float = Field(
        default=0.0,
        description="Overall elapsed time for the entire comparison request",
    )


class HealthResponse(BaseModel):
    """Response body for the health check endpoint."""

    status: str = Field(default="ok")
    version: str = Field(default="0.3.0")


# ──────────────────────────────────────────────────────────────
# Provider registry — all 9 supported providers
# ──────────────────────────────────────────────────────────────

ALL_PROVIDERS: list[str] = [
    "openai",
    "anthropic",
    "deepseek",
    "openrouter",
    "mimo",
    "gemini",
    "mistral",
    "cohere",
    "ollama",
]

# Map provider name → provider class
PROVIDER_CLASSES: dict[str, type] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "deepseek": DeepSeekProvider,
    "openrouter": OpenRouterProvider,
    "mimo": MiMoProvider,
    "gemini": GeminiProvider,
    "mistral": MistralProvider,
    "cohere": CohereProvider,
    "ollama": OllamaProvider,
}

# Default model for each provider
DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4",
    "anthropic": "claude-4-sonnet",
    "deepseek": "deepseek-v3",
    "openrouter": "openai/gpt-4",
    "mimo": "mimo-v2.5",
    "gemini": "gemini-2.5-flash",
    "mistral": "mistral-large-latest",
    "cohere": "command-a-plus-05-2026",
    "ollama": "gemma3",
}

# ──────────────────────────────────────────────────────────────
# SSRF Protection
# ──────────────────────────────────────────────────────────────

ALLOWED_SCHEMES = {"https", "http"}
BLOCKED_HOSTS: set[str] = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "169.254.169.254",
}
BLOCKED_IP_RANGES: list[str] = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "169.254.0.0/16",
]


def _validate_ssrf_in_prompt(prompt: str) -> bool:
    """Check if the prompt contains dangerous URLs targeting internal networks.

    Returns True if safe (no dangerous URLs found), False if a dangerous URL is present.
    """
    url_pattern = re.compile(r"https?://[^\s\"'<>()]+")
    urls = url_pattern.findall(prompt)
    for url in urls:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            hostname = parsed.hostname
            if not hostname:
                continue
            if hostname in BLOCKED_HOSTS:
                return False
            # Check if hostname resolves to a blocked IP range
            try:
                ip = ipaddress.ip_address(hostname)
                for net_str in BLOCKED_IP_RANGES:
                    if ip in ipaddress.ip_network(net_str, strict=False):
                        return False
            except ValueError:
                # Not an IP address — plain hostname, let it through
                pass
        except Exception:
            continue
    return True


# ──────────────────────────────────────────────────────────────
# Response highlight extraction
# ──────────────────────────────────────────────────────────────


def _extract_response_highlights(content: str) -> dict[str, int]:
    """Extract structure highlights from response text.

    Returns counts of code blocks, lists, tables, and JSON objects.
    """
    highlights: dict[str, int] = {}

    # Code blocks (fenced with ```)
    code_blocks = re.findall(r"```", content)
    highlights["code_blocks"] = len(code_blocks) // 2

    # Inline code (`code`)
    inline_code = re.findall(r"`[^`]+`", content)
    highlights["inline_code"] = len(inline_code)

    # Lists (lines starting with - or * or 1. 2. etc)
    list_items = re.findall(r"^\s*[-*]\s|\s*\\d+\\.\\s", content, re.MULTILINE)
    highlights["list_items"] = len(list_items)

    # Tables (lines with | separators)
    table_lines = [line for line in content.split("\n") if "|" in line]
    highlights["tables"] = len(table_lines) // 2 if table_lines else 0

    # JSON objects/blocks
    json_objects = re.findall(r"\{[^}]+\}", content)
    highlights["json_blocks"] = len(json_objects)

    return highlights


# ──────────────────────────────────────────────────────────────
# Rate limiting
# ──────────────────────────────────────────────────────────────

RATE_LIMIT_MAX: int = 20  # max requests per window
RATE_LIMIT_WINDOW: int = 60  # window in seconds

_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(client_ip: str) -> None:
    """Check and record a request against the rate limit.

    Raises HTTPException(429) if the client has exceeded the limit.
    """
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW
    timestamps = [t for t in _rate_limit_store[client_ip] if t > cutoff]
    if len(timestamps) >= RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded. "
                f"Max {RATE_LIMIT_MAX} requests per {RATE_LIMIT_WINDOW}s."
            ),
        )
    timestamps.append(now)
    _rate_limit_store[client_ip] = timestamps


def _reset_rate_limiter() -> None:
    """Clear all rate limit state (useful for testing)."""
    _rate_limit_store.clear()


# ──────────────────────────────────────────────────────────────
# Provider calling logic
# ──────────────────────────────────────────────────────────────


def _classify_provider_error(error: Exception) -> tuple[str, str]:
    """Map provider exceptions to stable categories and recovery guidance."""
    message = str(error).lower()
    credential_tokens = (
        "401",
        "403",
        "api key",
        "unauthorized",
        "authentication",
    )
    if any(token in message for token in credential_tokens):
        return (
            "credential_error",
            "Check the provider API key, refresh provider status, and retry.",
        )
    if any(token in message for token in ("429", "rate limit", "quota")):
        return (
            "quota_error",
            "Wait for quota recovery or reduce provider usage before retrying.",
        )
    if any(token in message for token in ("timeout", "timed out")):
        return (
            "timeout_error",
            "Retry the provider, or use a faster model or shorter prompt.",
        )
    network_tokens = ("connection", "network", "dns", "unreachable")
    if any(token in message for token in network_tokens):
        return (
            "network_error",
            "Check provider connectivity and network settings, then retry.",
        )
    if any(token in message for token in ("policy", "blocked", "not allowed")):
        return (
            "policy_error",
            "Review provider and model policy before retrying.",
        )
    return (
        "provider_error",
        "Retry this provider, then inspect its trace if the error repeats.",
    )

def _call_provider(
    provider_name: str,
    prompt: str,
    system_prompt: str | None = None,
) -> PlaygroundProviderResult:
    """Call a single provider and return a structured result.

    Latency (time-to-first-token, total), character count, and
    response highlights are computed automatically.  On error
    the result's ``error`` field is set instead of raising.
    """
    provider_cls = PROVIDER_CLASSES.get(provider_name)
    if provider_cls is None:
        return PlaygroundProviderResult(
            provider=provider_name,
            error=f"Unknown provider: {provider_name!r}",
        )

    default_model = DEFAULT_MODELS.get(provider_name, "unknown")
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        # Instantiate the provider (Ollama takes ``host``, others take ``api_key``)
        if provider_name == "ollama":
            provider = provider_cls(host=None, model=default_model)
        else:
            api_key = os.getenv(f"{provider_name.upper()}_API_KEY")
            provider = provider_cls(api_key=api_key, model=default_model)

        start = time.monotonic()

        # Use streaming for time-to-first-token measurement
        chunks: list[str] = []
        first_token_time: float | None = None
        for chunk in provider.stream(messages):
            if first_token_time is None:
                first_token_time = time.monotonic()
            chunks.append(chunk)

        total_end = time.monotonic()
        content = "".join(chunks)
        total_ms = (total_end - start) * 1000
        time_to_first = (
            (first_token_time - start) * 1000 if first_token_time else total_ms
        )

        # Fallback to chat() if streaming returned nothing (empty or not supported)
        if not chunks and not content:
            resp: LLMResponse = provider.chat(messages)
            content = resp.content
            total_ms = resp.latency_ms
            time_to_first = total_ms
            tokens_used = resp.tokens_used
            cost_usd = resp.cost_usd
        else:
            tokens_used = 0
            cost_usd = 0.0

        return PlaygroundProviderResult(
            content=content,
            provider=provider_name,
            model=default_model,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            latency=ProviderLatency(
                time_to_first_token_ms=round(time_to_first, 2),
                total_ms=round(total_ms, 2),
            ),
            character_count=len(content),
            response_highlights=_extract_response_highlights(content),
        )

    except Exception as exc:
        error_code, recovery_action = _classify_provider_error(exc)
        return PlaygroundProviderResult(
            content="",
            provider=provider_name,
            model=default_model,
            error=str(exc),
            error_code=error_code,
            recovery_action=recovery_action,
        )


# ──────────────────────────────────────────────────────────────
# FastAPI router
# ──────────────────────────────────────────────────────────────


def create_router() -> APIRouter:
    """Create and return the FastAPI APIRouter for playground endpoints.

    Includes:
      - POST /api/playground/compare — compare providers
      - GET  /health                 — health check
    """
    router = APIRouter()

    @router.post(
        "/api/playground/compare",
        response_model=PlaygroundCompareResponse,
    )
    def compare_endpoint(
        request: PlaygroundCompareRequest,
        http_request: Request,
    ) -> PlaygroundCompareResponse:
        """Compare the given prompt across requested providers.

        SSRF validation is applied to the prompt before any provider is called.
        Provider errors are captured per-result (not raised).  Rate limiting
        is enforced per client IP.
        """
        # ── Rate limit check ──
        client_ip = (
            http_request.client.host
            if http_request.client is not None
            else "unknown"
        )
        _check_rate_limit(client_ip)

        # ── SSRF check ──
        if not _validate_ssrf_in_prompt(request.prompt):
            raise HTTPException(
                status_code=422,
                detail=(
                "Prompt contains URLs targeting private/internal "
                "networks (SSRF blocked)"
            ),
            )

        # ── Provider validation ──
        provider_names = request.providers or list(ALL_PROVIDERS)
        invalid = [p for p in provider_names if p not in PROVIDER_CLASSES]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid provider(s): {', '.join(invalid)}. "
                f"Valid: {', '.join(ALL_PROVIDERS)}",
            )

        # ── Execute providers ──
        start_total = time.monotonic()
        results: dict[str, PlaygroundProviderResult] = {}
        for name in provider_names:
            results[name] = _call_provider(name, request.prompt, request.system_prompt)
        total_latency_ms = (time.monotonic() - start_total) * 1000

        return PlaygroundCompareResponse(
            results=results,
            total_latency_ms=round(total_latency_ms, 2),
        )

    @router.get("/api/playground/providers")
    def provider_readiness() -> dict[str, list[dict[str, Any]]]:
        """Return safe provider readiness metadata for the playground.

        Credential values are never returned. Hosted providers are considered
        configured when their documented API-key environment variable exists.
        Ollama is local and therefore reports configuration independently of a key.
        """
        providers = []
        for name in ALL_PROVIDERS:
            env_name = "CO_API_KEY" if name == "cohere" else f"{name.upper()}_API_KEY"
            local = name == "ollama"
            providers.append({
                "provider": name,
                "model": DEFAULT_MODELS[name],
                "configured": local or bool(os.getenv(env_name)),
                "local": local,
                "status": "ready" if local or os.getenv(env_name) else "setup_required",
            })
        return {"providers": providers}

    @router.get(
        "/health",
        response_model=HealthResponse,
    )
    def health_endpoint() -> HealthResponse:
        """Return health check information."""
        return HealthResponse()

    return router


router: Any = None
"""FastAPI APIRouter instance — set by create_router() at app startup."""
