"""Pre-dev tests for playground API endpoints (TASK-5).

Interface tests verify the API surface (must pass immediately against stubs).
Behavioral tests define expected behavior using FastAPI TestClient —
they will fail with NotImplementedError until the developer implements
the actual endpoint logic.

Coverage:
    - POST /api/playground/compare — success, error handling, latency,
      character count, response highlights, SSRF protection
    - GET /health — health check
    - Input validation (empty prompt, invalid provider names)

pytest markers:
    @pytest.mark.unit — mocked HTTP, no real API keys needed
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ai_vibe_coding.playground import (
    ALL_PROVIDERS,
    HealthResponse,
    PlaygroundCompareRequest,
    PlaygroundCompareResponse,
    PlaygroundProviderResult,
    ProviderLatency,
    _reset_rate_limiter,
    create_router,
)

# ──────────────────────────────────────────────────────────────
# Interface smoke tests (must PASS immediately against stubs)
# ──────────────────────────────────────────────────────────────


class TestPlaygroundInterfaceSmoke:
    """Verify all models, constants, and functions exist."""

    def test_import_playground_module(self):
        """Module should be importable."""
        from ai_vibe_coding import playground

        assert playground is not None

    def test_all_providers_has_nine(self):
        """ALL_PROVIDERS should list all 9 supported providers."""
        expected = [
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
        assert expected == ALL_PROVIDERS
        assert len(ALL_PROVIDERS) == 9

    def test_all_providers_unique(self):
        """ALL_PROVIDERS should contain no duplicates."""
        assert len(ALL_PROVIDERS) == len(set(ALL_PROVIDERS))

    # ── Pydantic model instantiation tests ──

    def test_provider_latency_defaults(self):
        """ProviderLatency should have sensible defaults."""
        lat = ProviderLatency()
        assert lat.time_to_first_token_ms == 0.0
        assert lat.total_ms == 0.0

    def test_provider_latency_custom(self):
        """ProviderLatency should accept custom values."""
        lat = ProviderLatency(time_to_first_token_ms=150.5, total_ms=1200.0)
        assert lat.time_to_first_token_ms == 150.5
        assert lat.total_ms == 1200.0

    def test_playground_provider_result_defaults(self):
        """PlaygroundProviderResult should have sensible defaults."""
        result = PlaygroundProviderResult()
        assert result.content == ""
        assert result.provider == ""
        assert result.model == ""
        assert result.tokens_used == 0
        assert result.cost_usd == 0.0
        assert isinstance(result.latency, ProviderLatency)
        assert result.character_count == 0
        assert result.response_highlights == {}
        assert result.error is None

    def test_playground_provider_result_full(self):
        """PlaygroundProviderResult should accept all fields."""
        result = PlaygroundProviderResult(
            content="Hello world",
            provider="openai",
            model="gpt-4",
            tokens_used=15,
            cost_usd=0.0002,
            latency=ProviderLatency(time_to_first_token_ms=100.0, total_ms=500.0),
            character_count=11,
            response_highlights={"code_blocks": 0, "lists": 1},
            error=None,
        )
        assert result.content == "Hello world"
        assert result.tokens_used == 15
        assert result.latency.time_to_first_token_ms == 100.0
        assert result.character_count == 11

    def test_playground_provider_result_error(self):
        """PlaygroundProviderResult should accept error string."""
        result = PlaygroundProviderResult(
            content="",
            provider="ollama",
            model="gemma3",
            error="Connection refused",
        )
        assert result.error == "Connection refused"

    def test_compare_request_requires_prompt(self):
        """PlaygroundCompareRequest should require prompt field."""
        req = PlaygroundCompareRequest(prompt="test prompt")
        assert req.prompt == "test prompt"
        assert req.providers is None  # default
        assert req.system_prompt is None  # default

    def test_compare_request_with_optional_fields(self):
        """PlaygroundCompareRequest should accept optional fields."""
        req = PlaygroundCompareRequest(
            prompt="hello",
            providers=["openai", "anthropic"],
            system_prompt="Be concise",
        )
        assert req.providers == ["openai", "anthropic"]
        assert req.system_prompt == "Be concise"

    def test_compare_response_defaults(self):
        """PlaygroundCompareResponse should have sensible defaults."""
        resp = PlaygroundCompareResponse()
        assert resp.results == {}
        assert resp.total_latency_ms == 0.0

    def test_health_response_defaults(self):
        """HealthResponse should have sensible defaults."""
        resp = HealthResponse()
        assert resp.status == "ok"
        assert resp.version == "0.3.0"

    def test_create_router_function_exists(self):
        """create_router should be a callable function."""
        assert callable(create_router)

    def test_router_constant_is_none_by_default(self):
        """router module-level constant should be None initially."""
        from ai_vibe_coding import playground

        assert playground.router is None

    # ── All-provider registry tests ──

    @pytest.mark.parametrize(
        "provider_name",
        [
            "openai",
            "anthropic",
            "deepseek",
            "openrouter",
            "mimo",
            "gemini",
            "mistral",
            "cohere",
            "ollama",
        ],
    )
    def test_all_providers_contains(self, provider_name):
        """ALL_PROVIDERS should contain each expected provider."""
        assert provider_name in ALL_PROVIDERS

    def test_llm_client_providers_matches_playground(self):
        """LLMClient.PROVIDERS keys should be a subset of ALL_PROVIDERS."""
        from ai_vibe_coding.llm_wrapper import LLMClient

        for prov in LLMClient.PROVIDERS:
            assert prov in ALL_PROVIDERS, (
                f"{prov} is in LLMClient but not in ALL_PROVIDERS"
            )

    def test_provider_examples_in_all_providers(self):
        """Additional providers (gemini, mistral, cohere, ollama) should be
        in ALL_PROVIDERS."""
        for extra in ["gemini", "mistral", "cohere", "ollama"]:
            assert extra in ALL_PROVIDERS, f"{extra} missing from ALL_PROVIDERS"


# ──────────────────────────────────────────────────────────────
# Helper for building mock provider results
# ──────────────────────────────────────────────────────────────


def _mock_result(
    provider_name: str, error: str | None = None
) -> PlaygroundProviderResult:
    """Build a plausible PlaygroundProviderResult for the named provider."""
    content = f"Response from {provider_name}" if error is None else ""
    return PlaygroundProviderResult(
        content=content,
        provider=provider_name,
        model="test-model",
        tokens_used=42,
        cost_usd=0.001,
        latency=ProviderLatency(time_to_first_token_ms=100.0, total_ms=500.0),
        character_count=len(content),
        response_highlights={"code_blocks": 0, "lists": 0},
        error=error,
    )


# ──────────────────────────────────────────────────────────────
# Behavioral pre-state tests (FAIL until developer implements)
# These test actual endpoint behavior via FastAPI TestClient.
# ──────────────────────────────────────────────────────────────


class TestPlaygroundCompare:
    """Behavioral tests for POST /api/playground/compare."""

    def setup_method(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(create_router())
        self.client = TestClient(app)

    def test_compare_returns_expected_structure(self):
        """POST /api/playground/compare should return a PlaygroundCompareResponse
        with results for all requested providers."""
        with patch(
            "ai_vibe_coding.playground._call_provider",
            return_value=_mock_result("openai"),
        ):
            resp = self.client.post(
                "/api/playground/compare",
                json={"prompt": "Hello"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total_latency_ms" in data
        for prov in ALL_PROVIDERS:
            assert prov in data["results"], f"Missing provider: {prov}"

    def test_compare_with_all_nine_providers(self):
        """Calling compare with no provider list should query all 9 providers."""
        with patch(
            "ai_vibe_coding.playground._call_provider",
            side_effect=lambda p, prompt, system_prompt=None: _mock_result(p),
        ) as mock_call:
            resp = self.client.post(
                "/api/playground/compare",
                json={"prompt": "Hello"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 9
        # Verify all 9 were actually called
        called = {call.args[0] for call in mock_call.call_args_list}
        assert called == set(ALL_PROVIDERS)

    def test_compare_with_subset_of_providers(self):
        """Compare should only query providers listed in the request."""
        subset = ["openai", "anthropic", "gemini"]
        with patch(
            "ai_vibe_coding.playground._call_provider",
            side_effect=lambda p, prompt, system_prompt=None: _mock_result(p),
        ) as mock_call:
            resp = self.client.post(
                "/api/playground/compare",
                json={"prompt": "Hello", "providers": subset},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == len(subset)
        called = {call.args[0] for call in mock_call.call_args_list}
        assert called == set(subset)

    def test_compare_with_system_prompt(self):
        """System prompt should be included in the messages sent to each provider."""
        with patch(
            "ai_vibe_coding.playground._call_provider",
            side_effect=lambda p, prompt, system_prompt=None: _mock_result(p),
        ) as mock_call:
            self.client.post(
                "/api/playground/compare",
                json={"prompt": "Hello", "system_prompt": "Be concise"},
            )
        # Every call should receive the system_prompt (passed positionally as 3rd arg)
        for call_args in mock_call.call_args_list:
            args = call_args[0]
            # args = (provider_name, prompt, system_prompt)
            assert len(args) >= 3, f"Expected 3 positional args, got {len(args)}"
            assert args[2] == "Be concise"

    def test_each_result_has_latency_data(self):
        """Each provider result should have latency.time_to_first_token_ms and
        latency.total_ms populated (non-zero)."""
        with patch(
            "ai_vibe_coding.playground._call_provider",
            side_effect=lambda p, prompt, system_prompt=None: _mock_result(p),
        ):
            resp = self.client.post(
                "/api/playground/compare",
                json={"prompt": "Hello"},
            )
        assert resp.status_code == 200
        for prov_name, result in resp.json()["results"].items():
            lat = result["latency"]
            assert lat["time_to_first_token_ms"] > 0, (
                f"{prov_name}: time_to_first_token_ms not positive"
            )
            assert lat["total_ms"] > 0, (
                f"{prov_name}: total_ms not positive"
            )

    def test_each_result_has_character_count(self):
        """Each provider result should have character_count > 0."""
        with patch(
            "ai_vibe_coding.playground._call_provider",
            side_effect=lambda p, prompt, system_prompt=None: _mock_result(p),
        ):
            resp = self.client.post(
                "/api/playground/compare",
                json={"prompt": "Hello"},
            )
        assert resp.status_code == 200
        results = resp.json()["results"]
        # All 9 providers should have character_count > 0
        # (mock content is "Response from {name}")
        for prov_name, result in results.items():
            assert result["character_count"] > 0, (
                f"{prov_name}: character_count is 0"
            )

    def test_each_result_has_response_highlights(self):
        """Each provider result should have response_highlights dict."""
        with patch(
            "ai_vibe_coding.playground._call_provider",
            side_effect=lambda p, prompt, system_prompt=None: _mock_result(p),
        ):
            resp = self.client.post(
                "/api/playground/compare",
                json={"prompt": "Hello"},
            )
        assert resp.status_code == 200
        for prov_name, result in resp.json()["results"].items():
            assert isinstance(result["response_highlights"], dict), (
                f"{prov_name}: response_highlights not a dict"
            )

    def test_compare_response_has_total_latency(self):
        """The top-level response should include total_latency_ms > 0."""
        with patch(
            "ai_vibe_coding.playground._call_provider",
            side_effect=lambda p, prompt, system_prompt=None: _mock_result(p),
        ):
            resp = self.client.post(
                "/api/playground/compare",
                json={"prompt": "Hello"},
            )
        assert resp.status_code == 200
        assert resp.json()["total_latency_ms"] > 0

    def test_compare_handles_provider_error_gracefully(self):
        """If one provider fails, the response should include an error for that
        provider but still include results for other providers."""
        def mock_with_one_error(provider_name, prompt, system_prompt=None):
            if provider_name == "openai":
                return _mock_result(provider_name, error="API rate limit exceeded")
            return _mock_result(provider_name)

        with patch(
            "ai_vibe_coding.playground._call_provider",
            side_effect=mock_with_one_error,
        ):
            resp = self.client.post(
                "/api/playground/compare",
                json={"prompt": "Hello"},
            )
        assert resp.status_code == 200
        data = resp.json()
        # The errored provider should have an error message
        assert data["results"]["openai"]["error"] is not None
        assert "rate limit" in data["results"]["openai"]["error"].lower()
        # Other providers should still have content
        for prov in ALL_PROVIDERS:
            if prov == "openai":
                continue
            assert data["results"][prov]["content"] != ""
            assert data["results"][prov]["error"] is None

    def test_compare_handles_all_providers_failing(self):
        """If all providers fail, each result should have error set."""
        def mock_all_errors(provider_name, prompt, system_prompt=None):
            return _mock_result(provider_name, error=f"{provider_name} is down")

        with patch(
            "ai_vibe_coding.playground._call_provider",
            side_effect=mock_all_errors,
        ):
            resp = self.client.post(
                "/api/playground/compare",
                json={"prompt": "Hello"},
            )
        assert resp.status_code == 200
        data = resp.json()
        for prov in ALL_PROVIDERS:
            assert data["results"][prov]["error"] is not None, (
                f"{prov} should have error set"
            )

    def test_compare_invalid_provider_name(self):
        """Request with an invalid provider name should return 422."""
        resp = self.client.post(
            "/api/playground/compare",
            json={"prompt": "Hello", "providers": ["nonexistent"]},
        )
        assert resp.status_code == 422

    def test_compare_empty_prompt(self):
        """Empty prompt should return 422 validation error."""
        resp = self.client.post(
            "/api/playground/compare",
            json={"prompt": ""},
        )
        assert resp.status_code == 422

    def test_compare_ssrf_protection_blocks_dangerous_urls(self):
        """The endpoint should reject requests containing URLs to private/internal
        networks (SSRF protection)."""
        dangerous_prompts = [
            "Check http://169.254.169.254/latest/meta-data/",
            "Read http://localhost:8080/admin",
            "Fetch http://127.0.0.1/secret",
            "Go to http://10.0.0.1/internal",
            "Open http://192.168.1.1/config",
        ]
        for prompt in dangerous_prompts:
            resp = self.client.post(
                "/api/playground/compare",
                json={"prompt": prompt},
            )
            assert resp.status_code == 422, (
                f"SSRF not blocked for: {prompt[:40]}..."
            )

    def test_compare_ssrf_protection_allows_safe_urls(self):
        """The endpoint should allow prompts with safe public URLs."""
        safe_prompts = [
            "Check https://example.com",
            "Read http://api.openai.com/docs",
            "What is https://github.com?",
        ]
        for prompt in safe_prompts:
            with patch(
                "ai_vibe_coding.playground._call_provider",
                return_value=_mock_result("openai"),
            ):
                resp = self.client.post(
                    "/api/playground/compare",
                    json={"prompt": prompt},
                )
            assert resp.status_code == 200, (
                f"Safe URL blocked: {prompt[:40]}..."
            )


class TestPlaygroundHealth:
    """Behavioral tests for GET /health."""

    def setup_method(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(create_router())
        self.client = TestClient(app)

    def test_health_returns_200(self):
        """GET /health should return 200 OK."""
        resp = self.client.get("/health")
        assert resp.status_code == 200

    def test_health_returns_expected_fields(self):
        """GET /health should return status and version."""
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.3.0"


class TestPlaygroundRateLimiting:
    """Behavioral tests for rate limiting on the compare endpoint."""

    def setup_method(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        _reset_rate_limiter()  # fresh slate for each test
        app = FastAPI()
        app.include_router(create_router())
        self.client = TestClient(app)

    def test_rate_limit_exceeded(self):
        """Rapid repeated requests should trigger rate limiting (429)."""
        mock_result = _mock_result("openai")

        # Fire RATE_LIMIT_MAX + 1 requests
        for i in range(21):
            with patch(
                "ai_vibe_coding.playground._call_provider",
                return_value=mock_result,
            ):
                resp = self.client.post(
                    "/api/playground/compare",
                    json={"prompt": "Hello"},
                )
            if i >= 20:  # request 21+ should be rate limited
                assert resp.status_code == 429, (
                    f"Request {i+1}: expected 429 got {resp.status_code}"
                )
            else:
                pass  # first 20 requests are within limit; don't assert
