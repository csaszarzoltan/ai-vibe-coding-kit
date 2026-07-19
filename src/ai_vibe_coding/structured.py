"""Structured output and tool calling support for LLM providers.

Provides JSON-mode chat completion and a function-calling abstraction
that works across all supported providers.

Public API:
    ToolDef         — dataclass defining a callable tool
    ToolCallResult  — dataclass for tool call responses
    LLMJSONError    — raised when provider returns invalid JSON
    ToolNotFoundError — raised when an unknown tool is requested
    chat_json()     — force JSON output from any provider
    chat_with_tools() — function calling across providers
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ai_vibe_coding.llm_wrapper import LLMClient, LLMResponse


class LLMJSONError(Exception):
    """Raised when a provider returns invalid JSON in JSON mode.

    Attributes:
        raw_response: The raw response text that failed to parse.
    """

    def __init__(self, message: str, raw_response: str = "") -> None:
        super().__init__(message)
        self.raw_response = raw_response


class ToolNotFoundError(Exception):
    """Raised when chat_with_tools() receives an unknown tool name."""


@dataclass
class ToolDef:
    """Definition of a callable tool for function calling.

    Attributes:
        name: Tool name (e.g. "get_weather").
        description: Human-readable description of what the tool does.
        parameters: JSON Schema dict describing accepted parameters.
    """

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallResult:
    """Result of a tool-calling LLM request.

    Attributes:
        tool_name: Name of the tool the LLM requested to call.
        arguments: Parsed JSON arguments dict.
        raw_response: The raw LLMResponse object.
    """

    tool_name: str
    arguments: dict[str, Any]
    raw_response: LLMResponse = field(default_factory=lambda: LLMResponse(
        content="", provider="", model="", tokens_used=0, cost_usd=0.0, latency_ms=0.0
    ))


def chat_json(
    client: LLMClient,
    prompt: str,
    *,
    system_prompt: str | None = None,
    schema: dict[str, Any] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Force JSON output from any provider and return parsed dict."""
    json_sys = "You must respond with valid JSON only. No markdown, no prose."
    if schema:
        json_sys += f" Follow this schema:\n{json.dumps(schema)}"
    full_sys = system_prompt if not system_prompt else f"{system_prompt}\n{json_sys}"
    if not system_prompt:
        full_sys = json_sys
    response = client.chat(
        prompt,
        system_prompt=full_sys,
        model=model,
    )
    content = response.content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMJSONError(
            f"Provider returned invalid JSON: {exc.msg}",
            raw_response=response.content,
        ) from exc
    return result


def chat_with_tools(
    client: LLMClient,
    prompt: str,
    tools: list[ToolDef],
    *,
    system_prompt: str | None = None,
    model: str | None = None,
) -> ToolCallResult:
    """Send a prompt with tool definitions and return the tool call."""
    tool_names = [t.name for t in tools]
    tool_desc = "\n".join(
        f"- {t.name}: {t.description}" for t in tools
    )
    tool_sys = (
        f"You have access to the following tools:\n{tool_desc}\n\n"
        f"Respond with a JSON object containing 'name' (the tool name) "
        f"and 'arguments' (a JSON object with the tool arguments). "
        f"Available tool names: {tool_names}"
    )
    full_sys = (
        f"{system_prompt}\n{tool_sys}" if system_prompt else tool_sys
    )
    response = client.chat(
        prompt,
        system_prompt=full_sys,
        model=model,
    )
    content = response.content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMJSONError(
            f"Tool call response is not valid JSON: {exc.msg}",
            raw_response=response.content,
        ) from exc
    tool_name = parsed.get("name", "")
    arguments = parsed.get("arguments", {})
    if tool_name not in tool_names:
        raise ToolNotFoundError(
            f"LLM requested unknown tool '{tool_name}'. "
            f"Available tools: {tool_names}"
        )
    return ToolCallResult(
        tool_name=tool_name,
        arguments=arguments,
        raw_response=response,
    )


__all__ = [
    "LLMJSONError",
    "ToolCallResult",
    "ToolDef",
    "ToolNotFoundError",
    "chat_json",
    "chat_with_tools",
]
