"""Structured output and tool calling support for LLM providers.

Provides JSON-mode chat completion and a function-calling abstraction
that works across all supported providers.

Public API:
    ToolDef              -- dataclass defining a callable tool
    ToolCallResult       -- dataclass for tool call responses
    LLMJSONError         -- raised when provider returns invalid JSON
    ToolNotFoundError    -- raised when chat_with_tools() receives an unknown tool name
    ApprovalDeniedError  -- raised when human approval is denied
    ApprovalChannel      -- protocol for approval channels
    chat_with_tools()    -- function calling across providers
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

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


class ApprovalDeniedError(Exception):
    """Raised when human approval is denied for a tool call.

    Attributes:
        tool_name: The name of the tool that was denied.
        arguments: The arguments that were passed to the tool.
    """

    def __init__(self, tool_name: str, arguments: dict[str, Any]) -> None:
        super().__init__(f"Human denied approval for tool '{tool_name}'")
        self.tool_name = tool_name
        self.arguments = arguments


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


class ApprovalChannel(Protocol):
    """Protocol for approval channels.

    Channels implement a __call__ method that:
    - Receives: tool_name (str), arguments (dict[str, Any])
    - Returns: True to approve, False to deny
    """

    def __call__(self, tool_name: str, arguments: dict[str, Any]) -> bool: ...


class CLIApprovalChannel:
    """CLI approval channel - prompts user via stdin for y/n approval."""

    def __init__(self, timeout: float = 60.0) -> None:
        """Initialize CLI approval channel.

        Args:
            timeout: Seconds to wait for user input before denying (default: 60.0).
        """
        self.timeout = timeout

    def __call__(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """Prompt user for approval via stdin."""
        # Print approval request
        print(
            f"\n🔐 Approval required for tool: {tool_name}",
            file=sys.stderr,
        )
        print(f"   Arguments: {json.dumps(arguments, indent=2)}", file=sys.stderr)
        print(
            f"   Approve? [y/N] (timeout: {self.timeout:.0f}s): ",
            end="", flush=True, file=sys.stderr,
        )

        # Use a thread to handle timeout
        result: dict[str, Any] = {"value": None, "done": False}

        def read_input() -> None:
            try:
                result["value"] = input().strip().lower()
            except (EOFError, KeyboardInterrupt):
                result["value"] = "n"
            finally:
                result["done"] = True

        thread = threading.Thread(target=read_input, daemon=True)
        thread.start()
        thread.join(timeout=self.timeout)

        if not result["done"]:
            print(" (timeout)", file=sys.stderr)
            return False

        answer = result["value"] or "n"
        approved = answer in ("y", "yes")
        print("   ✓ Approved" if approved else "   ✗ Denied", file=sys.stderr)
        return approved


class SlackApprovalChannel:
    """Slack approval channel - sends webhook and polls for response."""

    def __init__(
        self,
        webhook_url: str,
        polling_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> None:
        """Initialize Slack approval channel.

        Args:
            webhook_url: Slack incoming webhook URL.
            polling_interval: Seconds between polling for response (default: 2.0).
            timeout: Max seconds to wait for approval (default: 300.0).
        """
        self.webhook_url = webhook_url
        self.polling_interval = polling_interval
        self.timeout = timeout

    def __call__(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """Send approval request to Slack and poll for response."""
        import requests

        payload = {
            "text": (
                f"\U0001f510 *Approval Required*\n*Tool:* `{tool_name}`\n"
                f"*Arguments:* ```{json.dumps(arguments, indent=2)}```"
                "\n\nReact with \u2705 to approve or \u274c to deny."
            ),
        }
        try:
            requests.post(self.webhook_url, json=payload, timeout=10)
        except Exception as e:
            print(f"Slack webhook failed: {e}", file=sys.stderr)
            return False

        # Poll for reaction - simplified polling approach
        # In production, this would use Slack's Events API or a callback URL
        # For now, we'll poll a simple response endpoint or use reactions
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            # In a real implementation, you'd check for reactions or responses
            # This is a simplified placeholder
            time.sleep(self.polling_interval)

        # Timeout - deny by default
        return False


class TelegramApprovalChannel:
    """Telegram approval channel - sends message and polls for callback."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str | int,
        polling_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> None:
        """Initialize Telegram approval channel.

        Args:
            bot_token: Telegram bot token.
            chat_id: Target chat ID for approval message.
            polling_interval: Seconds between polling (default: 2.0).
            timeout: Max seconds to wait for approval (default: 300.0).
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.polling_interval = polling_interval
        self.timeout = timeout

    def __call__(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """Send approval request to Telegram and wait for callback."""
        import requests

        # Send approval message with inline keyboard
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        args_json = json.dumps(arguments, indent=2)
        payload = {
            "chat_id": self.chat_id,
            "text": (
                f"\U0001f510 *Approval Required*\n*Tool:* `{tool_name}`\n"
                f"*Arguments:* ```{args_json}```"
            ),
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "✅ Approve", "callback_data": f"approve:{tool_name}"},
                        {"text": "❌ Deny", "callback_data": f"deny:{tool_name}"},
                    ]
                ]
            },
        }
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Telegram send failed: {e}", file=sys.stderr)
            return False

        # Poll for callback query
        start_time = time.time()
        offset = 0
        while time.time() - start_time < self.timeout:
            try:
                get_url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
                resp = requests.get(
                    get_url,
                    params={"offset": offset, "timeout": 10},
                    timeout=15,
                )
                data = resp.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    if "callback_query" in update:
                        query = update["callback_query"]
                        if query["data"].startswith("approve:"):
                            return True
                        if query["data"].startswith("deny:"):
                            return False
            except Exception as e:
                print(f"Telegram poll failed: {e}", file=sys.stderr)
            time.sleep(self.polling_interval)

        return False


class CallableApprovalChannel:
    """Custom callable approval channel - wraps a user-provided callable."""

    def __init__(self, func: Callable[[str, dict[str, Any]], bool]) -> None:
        """Initialize with a callable.

        Args:
            func: Callable taking (tool_name, arguments) -> bool
                (True=approve, False=deny).
        """
        self.func = func

    def __call__(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """Delegate to the wrapped callable."""
        return self.func(tool_name, arguments)


# Channel type for convenience
ApprovalChannelType = (
    Literal["cli"] | Literal["slack"] | Literal["telegram"]
    | Callable[[str, dict[str, Any]], bool] | ApprovalChannel
)


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
    require_approval: dict[str, ApprovalChannelType] | None = None,
) -> ToolCallResult:
    """Send a prompt with tool definitions and return the tool call.

    Args:
        client: LLMClient instance.
        prompt: User prompt.
        tools: List of ToolDef objects describing available tools.
        system_prompt: Optional system prompt.
        model: Optional model override.
        require_approval: Optional dict mapping tool names to approval channels.
            Channels can be: "cli" (stdin prompt), "slack" (webhook), "telegram" (bot),
            a callable (tool_name, args) -> bool, or an ApprovalChannel instance.

    Returns:
        ToolCallResult with the called tool name and arguments.

    Raises:
        ToolNotFoundError: If LLM requests an unknown tool.
        ApprovalDeniedError: If human approval is denied for a gated tool.
    """
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

    # Check if this tool requires approval
    if require_approval and tool_name in require_approval:
        channel_spec = require_approval[tool_name]
        # Resolve channel spec to an actual channel callable
        channel = _resolve_approval_channel(channel_spec)
        approved = channel(tool_name, arguments)
        if not approved:
            raise ApprovalDeniedError(tool_name, arguments)

    return ToolCallResult(
        tool_name=tool_name,
        arguments=arguments,
        raw_response=response,
    )


def _resolve_approval_channel(
    channel_spec: ApprovalChannelType,
) -> ApprovalChannel:
    """Convert a channel specification into an ApprovalChannel instance."""
    if isinstance(channel_spec, str):
        if channel_spec == "cli":
            return CLIApprovalChannel()
        elif channel_spec == "slack":
            webhook_url = os.environ.get("SLACK_APPROVAL_WEBHOOK")
            if not webhook_url:
                raise ValueError(
                    "Slack approval requires SLACK_APPROVAL_WEBHOOK "
                    "environment variable"
                )
            return SlackApprovalChannel(webhook_url)
        elif channel_spec == "telegram":
            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
            chat_id = os.environ.get("TELEGRAM_APPROVAL_CHAT_ID")
            if not bot_token or not chat_id:
                raise ValueError(
                    "Telegram approval requires TELEGRAM_BOT_TOKEN "
                    "and TELEGRAM_APPROVAL_CHAT_ID environment variables"
                )
            return TelegramApprovalChannel(bot_token, chat_id)
        else:
            raise ValueError(f"Unknown approval channel: {channel_spec}")
    elif callable(channel_spec):
        # Check if it's already an ApprovalChannel instance
        if (
            callable(channel_spec)
            and channel_spec.__class__.__name__.endswith("ApprovalChannel")
        ):
            return channel_spec
        # Otherwise wrap in CallableApprovalChannel
        return CallableApprovalChannel(channel_spec)
    else:
        raise ValueError(f"Invalid approval channel specification: {channel_spec}")


__all__ = [
    "LLMJSONError",
    "ToolCallResult",
    "ToolDef",
    "ToolNotFoundError",
    "ApprovalDeniedError",
    "ApprovalChannel",
    "CLIApprovalChannel",
    "SlackApprovalChannel",
    "TelegramApprovalChannel",
    "CallableApprovalChannel",
    "chat_json",
    "chat_with_tools",
]
