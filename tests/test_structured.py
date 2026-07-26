"""Smoke tests for structured output and tool calling (TASK-2).

Interface tests verify API surface. Behavioral tests define the contract
for JSON mode and function calling across providers.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ai_vibe_coding.llm_wrapper import LLMClient, LLMResponse
from ai_vibe_coding.structured import (
    LLMJSONError,
    ToolCallResult,
    ToolDef,
    ToolNotFoundError,
    ApprovalDeniedError,
    CLIApprovalChannel,
    CallableApprovalChannel,
    chat_json,
    chat_with_tools,
)

# ──────────────────────────────────────────────────────────────
# Interface smoke tests
# ──────────────────────────────────────────────────────────────


class TestInterfaceSmoke:
    """Verify that all classes and functions exist with correct signatures."""

    def test_tool_def_is_dataclass(self):
        """ToolDef should be instantiable with name, description, parameters."""
        tool = ToolDef(
            name="get_weather",
            description="Get current weather for a city",
            parameters={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        )
        assert tool.name == "get_weather"
        assert tool.description == "Get current weather for a city"
        assert "properties" in tool.parameters

    def test_tool_def_default_parameters(self):
        """ToolDef should default parameters to empty dict."""
        tool = ToolDef(name="test", description="test tool")
        assert tool.parameters == {}

    def test_tool_call_result_is_dataclass(self):
        """ToolCallResult should have tool_name, arguments, raw_response."""
        result = ToolCallResult(
            tool_name="get_weather",
            arguments={"city": "Zurich"},
        )
        assert result.tool_name == "get_weather"
        assert result.arguments == {"city": "Zurich"}
        assert result.raw_response is not None

    def test_llm_json_error_has_raw_response(self):
        """LLMJSONError should store raw_response attribute."""
        err = LLMJSONError("Invalid JSON", raw_response="not json at all")
        assert err.raw_response == "not json at all"
        assert "Invalid JSON" in str(err)

    def test_tool_not_found_error_exists(self):
        """ToolNotFoundError should be an Exception."""
        assert issubclass(ToolNotFoundError, Exception)

    def test_approval_denied_error_exists(self):
        """ApprovalDeniedError should be an Exception with tool_name and arguments."""
        assert issubclass(ApprovalDeniedError, Exception)
        err = ApprovalDeniedError("send_email", {"to": "test@example.com"})
        assert err.tool_name == "send_email"
        assert err.arguments == {"to": "test@example.com"}

    def test_chat_json_is_callable(self):
        """chat_json should be a callable function."""
        assert callable(chat_json)

    def test_chat_with_tools_is_callable(self):
        """chat_with_tools should be a callable function."""
        assert callable(chat_with_tools)

    def test_cli_approval_channel_exists(self):
        """CLIApprovalChannel should be instantiable."""
        channel = CLIApprovalChannel(timeout=30.0)
        assert channel.timeout == 30.0

    def test_callable_approval_channel_exists(self):
        """CallableApprovalChannel should wrap a callable."""
        def approve_all(tool: str, args: dict) -> bool:
            return True
        channel = CallableApprovalChannel(approve_all)
        assert channel("any_tool", {}) is True


# ──────────────────────────────────────────────────────────────
# Behavioral pre-state tests (fail until implementation)
# ──────────────────────────────────────────────────────────────


class TestChatJson:
    """Behavioral tests for chat_json() — fail until implemented."""

    @pytest.mark.unit
    def test_chat_json_returns_parsed_dict(self):
        """chat_json() should return a parsed JSON dict from the provider."""
        with patch.object(LLMClient, "chat") as mock_chat:
            mock_chat.return_value = LLMResponse(
                content='{"answer": 42}',
                provider="openai",
                model="gpt-4",
                tokens_used=10,
                cost_usd=0.0001,
                latency_ms=50.0,
            )
            client = LLMClient(provider="openai", api_key="fake")
            result = chat_json(client, "What is the answer?")

        assert isinstance(result, dict)
        assert result["answer"] == 42

    @pytest.mark.unit
    def test_chat_json_raises_on_invalid_json(self):
        """chat_json() should raise LLMJSONError when response is not valid JSON."""
        with patch.object(LLMClient, "chat") as mock_chat:
            mock_chat.return_value = LLMResponse(
                content="This is not JSON at all",
                provider="openai",
                model="gpt-4",
                tokens_used=10,
                cost_usd=0.0001,
                latency_ms=50.0,
            )
            client = LLMClient(provider="openai", api_key="fake")
            with pytest.raises(LLMJSONError) as exc_info:
                chat_json(client, "Give me JSON")

        assert exc_info.value.raw_response == "This is not JSON at all"


class TestChatWithTools:
    """Behavioral tests for chat_with_tools() — fail until implemented."""

    @pytest.mark.unit
    def test_chat_with_tools_returns_tool_call_result(self):
        """chat_with_tools() should return a ToolCallResult."""
        weather_tool = ToolDef(
            name="get_weather",
            description="Get weather for a city",
            parameters={"type": "object", "properties": {"city": {"type": "string"}}},
        )
        with patch.object(LLMClient, "chat") as mock_chat:
            mock_chat.return_value = LLMResponse(
                content='{"name": "get_weather", "arguments": {"city": "Zurich"}}',
                provider="openai",
                model="gpt-4",
                tokens_used=20,
                cost_usd=0.0002,
                latency_ms=80.0,
            )
            client = LLMClient(provider="openai", api_key="fake")
            result = chat_with_tools(
                client, "What's the weather in Zurich?", [weather_tool]
            )

        assert isinstance(result, ToolCallResult)
        assert result.tool_name == "get_weather"
        assert result.arguments == {"city": "Zurich"}

    @pytest.mark.unit
    def test_chat_with_tools_raises_on_unknown_tool(self):
        """chat_with_tools() should raise ToolNotFoundError for unknown tools."""
        weather_tool = ToolDef(
            name="get_weather",
            description="Get weather",
        )
        with patch.object(LLMClient, "chat") as mock_chat:
            mock_chat.return_value = LLMResponse(
                content='{"name": "unknown_tool", "arguments": {}}',
                provider="openai",
                model="gpt-4",
                tokens_used=10,
                cost_usd=0.0001,
                latency_ms=50.0,
            )
            client = LLMClient(provider="openai", api_key="fake")
            with pytest.raises(ToolNotFoundError):
                chat_with_tools(client, "Do something", [weather_tool])

    @pytest.mark.unit
    def test_chat_with_tools_requires_approval_cli(self):
        """chat_with_tools() should prompt for approval when require_approval is set."""
        weather_tool = ToolDef(
            name="get_weather",
            description="Get weather",
            parameters={"type": "object", "properties": {"city": {"type": "string"}}},
        )
        with patch.object(LLMClient, "chat") as mock_chat:
            mock_chat.return_value = LLMResponse(
                content='{"name": "get_weather", "arguments": {"city": "Zurich"}}',
                provider="openai",
                model="gpt-4",
                tokens_used=20,
                cost_usd=0.0002,
                latency_ms=80.0,
            )
            client = LLMClient(provider="openai", api_key="fake")
            # Mock the CLI approval to return True (approve)
            with patch.object(CLIApprovalChannel, "__call__", return_value=True) as mock_approve:
                result = chat_with_tools(
                    client,
                    "What's the weather in Zurich?",
                    [weather_tool],
                    require_approval={"get_weather": "cli"},
                )

        assert isinstance(result, ToolCallResult)
        assert result.tool_name == "get_weather"
        mock_approve.assert_called_once_with("get_weather", {"city": "Zurich"})

    @pytest.mark.unit
    def test_chat_with_tools_denies_approval(self):
        """chat_with_tools() should raise ApprovalDeniedError when approval is denied."""
        delete_tool = ToolDef(
            name="delete_user",
            description="Delete a user",
            parameters={"type": "object", "properties": {"user_id": {"type": "string"}}},
        )
        with patch.object(LLMClient, "chat") as mock_chat:
            mock_chat.return_value = LLMResponse(
                content='{"name": "delete_user", "arguments": {"user_id": "123"}}',
                provider="openai",
                model="gpt-4",
                tokens_used=20,
                cost_usd=0.0002,
                latency_ms=80.0,
            )
            client = LLMClient(provider="openai", api_key="fake")
            # Mock the CLI approval to return False (deny)
            with patch.object(CLIApprovalChannel, "__call__", return_value=False):
                with pytest.raises(ApprovalDeniedError) as exc_info:
                    chat_with_tools(
                        client,
                        "Delete user 123",
                        [delete_tool],
                        require_approval={"delete_user": "cli"},
                    )

        assert exc_info.value.tool_name == "delete_user"
        assert exc_info.value.arguments == {"user_id": "123"}

    @pytest.mark.unit
    def test_chat_with_tools_custom_callable_approval(self):
        """chat_with_tools() should accept custom callable for approval."""
        send_email_tool = ToolDef(
            name="send_email",
            description="Send an email",
            parameters={"type": "object", "properties": {"to": {"type": "string"}}},
        )
        with patch.object(LLMClient, "chat") as mock_chat:
            mock_chat.return_value = LLMResponse(
                content='{"name": "send_email", "arguments": {"to": "test@example.com"}}',
                provider="openai",
                model="gpt-4",
                tokens_used=20,
                cost_usd=0.0002,
                latency_ms=80.0,
            )
            client = LLMClient(provider="openai", api_key="fake")
            # Custom approval function that approves only specific recipients
            def custom_approve(tool: str, args: dict) -> bool:
                return args.get("to") == "allowed@example.com"

            # This should be denied
            with pytest.raises(ApprovalDeniedError):
                chat_with_tools(
                    client,
                    "Send email",
                    [send_email_tool],
                    require_approval={"send_email": custom_approve},
                )

            # This should be approved
            mock_chat.return_value = LLMResponse(
                content='{"name": "send_email", "arguments": {"to": "allowed@example.com"}}',
                provider="openai",
                model="gpt-4",
                tokens_used=20,
                cost_usd=0.0002,
                latency_ms=80.0,
            )
            result = chat_with_tools(
                client,
                "Send email",
                [send_email_tool],
                require_approval={"send_email": custom_approve},
            )
            assert result.tool_name == "send_email"
            assert result.arguments == {"to": "allowed@example.com"}

    @pytest.mark.unit
    def test_chat_with_tools_no_approval_for_ungated_tool(self):
        """chat_with_tools() should not require approval for tools not in require_approval."""
        weather_tool = ToolDef(
            name="get_weather",
            description="Get weather",
        )
        send_email_tool = ToolDef(
            name="send_email",
            description="Send email",
        )
        with patch.object(LLMClient, "chat") as mock_chat:
            mock_chat.return_value = LLMResponse(
                content='{"name": "get_weather", "arguments": {"city": "Zurich"}}',
                provider="openai",
                model="gpt-4",
                tokens_used=20,
                cost_usd=0.0002,
                latency_ms=80.0,
            )
            client = LLMClient(provider="openai", api_key="fake")
            # Only send_email requires approval
            result = chat_with_tools(
                client,
                "What's the weather?",
                [weather_tool, send_email_tool],
                require_approval={"send_email": "cli"},
            )

        assert result.tool_name == "get_weather"
        # No approval should have been requested for get_weather
