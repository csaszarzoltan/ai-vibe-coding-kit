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

    def test_chat_json_is_callable(self):
        """chat_json should be a callable function."""
        assert callable(chat_json)

    def test_chat_with_tools_is_callable(self):
        """chat_with_tools should be a callable function."""
        assert callable(chat_with_tools)


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
