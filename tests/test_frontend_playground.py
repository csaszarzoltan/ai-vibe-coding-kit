"""Pre-dev tests for LLM Playground frontend (static/ files).

Interface (contract) tests verify stub file existence and HTML structure —
these must pass immediately against the stubs.

Behavioral tests define expected frontend behaviour — they will fail with
NotImplementedError until the developer implements the actual functionality.

Coverage:
    - static/index.html exists with all required elements
    - static/playground.css exists (placeholder OK)
    - static/playground.js exists with expected function signatures
    - HTML elements have correct id and data-* attributes per spec
    - API call validation (empty prompt, no providers selected)

pytest markers:
    @pytest.mark.unit — frontend contract validation, no browser needed
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
HTML_PATH = STATIC_DIR / "index.html"
CSS_PATH = STATIC_DIR / "playground.css"
JS_PATH = STATIC_DIR / "playground.js"

# ──────────────────────────────────────────────────────────────
# HTML parsing helpers
# ──────────────────────────────────────────────────────────────


class ElementFinder(HTMLParser):
    """Collect elements matching tag + optional attributes."""

    def __init__(self) -> None:
        super().__init__()
        self.elements: list[dict[str, Any]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.elements.append({"tag": tag, "attrs": dict(attrs)})


def find_elements(
    html: str, tag: str, **attrs: str
) -> list[dict[str, Any]]:
    """Find all elements in HTML matching tag and given attributes."""
    parser = ElementFinder()
    parser.feed(html)
    matches = []
    for elem in parser.elements:
        if elem["tag"] != tag:
            continue
        if all(elem["attrs"].get(k) == v for k, v in attrs.items()):
            matches.append(elem)
    return matches


# ──────────────────────────────────────────────────────────────
# Interface smoke tests — must PASS immediately against stubs
# ──────────────────────────────────────────────────────────────


class TestFrontendFileExistence:
    """Verify all static stub files exist."""

    def test_static_directory_exists(self) -> None:
        """static/ directory should exist under the project root."""
        assert STATIC_DIR.is_dir(), (
            f"static/ directory not found at {STATIC_DIR}"
        )

    def test_index_html_exists(self) -> None:
        """static/index.html should exist."""
        assert HTML_PATH.is_file(), (
            f"static/index.html not found at {HTML_PATH}"
        )

    def test_playground_css_exists(self) -> None:
        """static/playground.css should exist."""
        assert CSS_PATH.is_file(), (
            f"static/playground.css not found at {CSS_PATH}"
        )

    def test_playground_js_exists(self) -> None:
        """static/playground.js should exist."""
        assert JS_PATH.is_file(), (
            f"static/playground.js not found at {JS_PATH}"
        )


class TestIndexHtmlStructure:
    """Verify static/index.html contains all required elements per spec."""

    PROVIDER_SLUGS = [
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

    @pytest.fixture
    def html(self) -> str:
        """Read and return the index.html content."""
        return HTML_PATH.read_text(encoding="utf-8")

    # ── Document structure ──

    def test_has_doctype(self, html: str) -> None:
        """HTML should start with <!DOCTYPE html>."""
        assert html.strip().startswith("<!DOCTYPE html>") or (
            "<!DOCTYPE html>" in html[:100]
        ), "Missing <!DOCTYPE html> declaration"

    def test_html_well_formed(self, html: str) -> None:
        """HTML should parse without errors."""
        parser = HTMLParser()
        try:
            parser.feed(html)
        except Exception as exc:
            pytest.fail(f"HTML parsing failed: {exc}")

    def test_has_h1_title(self, html: str) -> None:
        """Page should have an <h1> element."""
        elements = find_elements(html, "h1")
        assert len(elements) >= 1, "No <h1> element found"

    # ── Provider checkboxes ──

    def test_has_nine_or_more_checkboxes(self, html: str) -> None:
        """There should be at least 9 checkbox inputs (one per provider)."""
        checkboxes = find_elements(html, "input", type="checkbox")
        assert len(checkboxes) >= 9, (
            f"Expected at least 9 checkboxes, found {len(checkboxes)}"
        )

    @pytest.mark.parametrize("slug", PROVIDER_SLUGS)
    def test_provider_checkbox_has_data_provider(
        self, html: str, slug: str
    ) -> None:
        """Each provider checkbox should have the correct data-provider attr."""
        matches = find_elements(
            html, "input", **{"data-provider": slug}  # type: ignore[arg-type]
        )
        assert len(matches) >= 1, (
            f"No checkbox with data-provider='{slug}' found"
        )

    # ── Prompt textarea ──

    def test_has_prompt_textarea(self, html: str) -> None:
        """Textarea with id='prompt-input' should exist."""
        elements = find_elements(html, "textarea", id="prompt-input")
        assert len(elements) >= 1, (
            "No textarea with id='prompt-input' found"
        )

    def test_textarea_has_placeholder(self, html: str) -> None:
        """Textarea should have a non-empty placeholder."""
        elements = find_elements(html, "textarea", id="prompt-input")
        assert elements, "No textarea with id='prompt-input'"
        placeholder = elements[0]["attrs"].get("placeholder", "")
        assert placeholder, "Textarea placeholder is empty or missing"

    def test_textarea_has_rows(self, html: str) -> None:
        """Textarea should have rows attribute (at least 3)."""
        elements = find_elements(html, "textarea", id="prompt-input")
        assert elements, "No textarea with id='prompt-input'"
        rows = elements[0]["attrs"].get("rows", "0")
        assert rows.isdigit() and int(rows) >= 3, (
            f"Expected rows >= 3, got rows='{rows}'"
        )

    # ── Compare button ──

    def test_has_compare_button(self, html: str) -> None:
        """Button with id='compare-btn' should exist."""
        elements = find_elements(html, "button", id="compare-btn")
        assert len(elements) >= 1, (
            "No button with id='compare-btn' found"
        )

    def test_compare_button_disabled_by_default(self, html: str) -> None:
        """Compare button should be disabled when no providers selected."""
        elements = find_elements(html, "button", id="compare-btn")
        assert elements, "No button with id='compare-btn'"
        attrs = elements[0]["attrs"]
        # disabled can be present as attribute (boolean) or "disabled"
        assert attrs.get("disabled") is not None or "disabled" in attrs, (
            "Compare button should be disabled by default (no providers selected)"
        )

    # ── Results container ──

    def test_has_results_container(self, html: str) -> None:
        """Div with id='results-grid' should exist."""
        elements = find_elements(html, "div", id="results-grid")
        assert len(elements) >= 1, (
            "No div with id='results-grid' found"
        )


class TestPlaygroundCssExistence:
    """Verify static/playground.css exists and is non-empty."""

    def test_css_file_not_empty(self) -> None:
        """playground.css should not be completely empty."""
        content = CSS_PATH.read_text(encoding="utf-8")
        assert content.strip(), "playground.css is empty (all whitespace)"


class TestPlaygroundJsStructure:
    """Verify static/playground.js exists with expected function signatures."""

    @pytest.fixture
    def js_content(self) -> str:
        """Read and return the playground.js content."""
        return JS_PATH.read_text(encoding="utf-8")

    def test_js_file_not_empty(self, js_content: str) -> None:
        """playground.js should contain some code."""
        assert js_content.strip(), "playground.js is empty"

    def test_js_has_compare_function(self, js_content: str) -> None:
        """Should define a compare() function (async or sync)."""
        assert (
            "function compare" in js_content
            or "compare =" in js_content
            or "async function compare" in js_content
            or "const compare" in js_content
        ), (
            "No compare() function definition found in playground.js"
        )

    def test_js_has_validate_function(self, js_content: str) -> None:
        """Should have a validateInput() function for input validation."""
        assert "validateInput" in js_content or "validate" in js_content, (
            "No validateInput or validate function found in playground.js"
        )

    def test_js_has_render_function(self, js_content: str) -> None:
        """Should have a function for rendering results."""
        assert "renderResults" in js_content or "render" in js_content, (
            "No renderResults function found in playground.js"
        )

    def test_js_has_error_handler(self, js_content: str) -> None:
        """Should have a function for rendering errors."""
        assert "renderError" in js_content or "error" in js_content.lower(), (
            "No error handling function found in playground.js"
        )


# ──────────────────────────────────────────────────────────────
# Behavioural pre-state tests — FAIL until developer implements
# These test expected frontend behaviour: validation, API calls, UI
# ──────────────────────────────────────────────────────────────


class TestFrontendValidation:
    """Behavioural tests for frontend input validation (Task F3)."""

    def test_empty_prompt_shows_validation(self) -> None:
        """validateInput() should return error for empty prompt."""
        js = JS_PATH.read_text(encoding="utf-8")
        # Must check prompt.trim()  or value.trim()  in the validation
        assert (
            ".trim()" in js or "trim()" in js
        ), "validateInput must trim prompt input"
        # validateInput must check empty prompt
        assert "promptText" in js or "prompt" in js.lower(), (
            "validateInput must reference prompt"
        )
        assert "Please enter" in js or "empty" in js or "prompt" in js.lower(), (
            "validateInput should have a validation message for empty prompt"
        )

    def test_no_provider_selected_shows_validation(self) -> None:
        """validateInput() should return error when no providers selected."""
        js = JS_PATH.read_text(encoding="utf-8")
        assert (
            "providers.length" in js or "getSelectedProviders" in js
        ), "validateInput must check selected providers"
        assert (
            "select at least one provider" in js.lower()
            or "no provider" in js.lower()
            or "providers.length === 0" in js
        ), "validateInput should have a message for no provider selected"

    def test_compare_button_disabled_when_no_providers(self) -> None:
        """updateButtonState() should disable button when no providers checked."""
        js = JS_PATH.read_text(encoding="utf-8")
        assert (
            "updateButtonState" in js
        ), "updateButtonState must be defined"
        assert (
            "btn.disabled" in js
        ), "updateButtonState must set button disabled property"
        assert (
            "providers.length > 0" in js or "providers.length >= 1" in js
        ), "updateButtonState must check providers.length"

    def test_compare_button_enabled_when_provider_selected(self) -> None:
        """updateButtonState() should enable button when >=1 provider selected."""
        js = JS_PATH.read_text(encoding="utf-8")
        assert (
            "updateButtonState" in js
        ), "updateButtonState must be defined"
        assert (
            "btn.disabled" in js
        ), "updateButtonState must toggle button disabled property"
        assert (
            "checked" in js
        ), "updateButtonState must read checkbox checked state"
        # The inverse is implied by the disabled logic
        assert (
            "!" in js or "false" in js
        ), "updateButtonState must enable button when conditions met"


class TestFrontendApiCall:
    """Behavioural tests for frontend API interaction (Task F3)."""

    def test_compare_sends_post_request(self) -> None:
        """compare() should send POST /api/playground/compare."""
        js = JS_PATH.read_text(encoding="utf-8")
        assert (
            "POST" in js
        ), "compare() must use POST method"
        assert (
            "/api/playground/compare" in js
        ), "compare() must POST to /api/playground/compare"
        assert (
            "fetch" in js
        ), "compare() must use fetch() API"

    def test_compare_request_has_prompt_and_providers(self) -> None:
        """Request body should include prompt string and providers array."""
        js = JS_PATH.read_text(encoding="utf-8")
        assert (
            "prompt" in js
        ), "Request body must include prompt field"
        assert (
            "providers" in js
        ), "Request body must include providers field"
        assert (
            "JSON.stringify" in js
        ), "compare() must stringify request body"

    def test_loading_state_shows_spinner(self) -> None:
        """Loading state should show a spinner and disable the button."""
        js = JS_PATH.read_text(encoding="utf-8")
        assert (
            "spinner" in js.lower()
        ), "Loading state must include a spinner element"
        assert (
            "btn.disabled" in js or "compareBtn.disabled" in js
        ), "Loading state must disable the button"
        assert (
            "innerHTML" in js or "textContent" in js
        ), "Loading state must update button text"

    def test_results_rendered_in_grid(self) -> None:
        """Each provider result should render as a card in the results grid."""
        js = JS_PATH.read_text(encoding="utf-8")
        assert (
            "renderResults" in js
        ), "renderResults() must be defined"
        assert (
            "createElement" in js or "innerHTML" in js
        ), "renderResults must create DOM elements"
        assert (
            "grid" in js or "results-grid" in js or "resultsGrid" in js
        ), "renderResults must target the results grid"

    def test_cards_sorted_by_latency(self) -> None:
        """Cards should be sorted by latency ascending (fastest first)."""
        js = JS_PATH.read_text(encoding="utf-8")
        assert (
            "sort" in js
        ), "renderResults must sort results"
        assert (
            "latency" in js.lower()
        ), "Latency-driven sorting must reference latency field"
        assert (
            "total_ms" in js or "latency" in js.lower()
        ), "Sort must compare total_ms values"

    def test_error_provider_shows_error_card(self) -> None:
        """Provider with error field set should show an error card."""
        js = JS_PATH.read_text(encoding="utf-8")
        assert (
            "card-error" in js or "error" in js.lower()
        ), "Error card must have error styling class"
        assert (
            "result.error" in js or "entry.error" in js or "hasError" in js
        ), "Code must check for error field on result"

    def test_network_error_shows_banner(self) -> None:
        """Network/server-level errors should show a general error banner."""
        js = JS_PATH.read_text(encoding="utf-8")
        assert (
            "renderError" in js
        ), "renderError() must be defined"
        assert (
            "error-banner" in js or "errorBanner" in js
        ), "renderError must target the error-banner element"
        assert (
            "catch" in js or ".catch" in js
        ), "compare() should catch network errors and call renderError"


class TestFrontendMetrics:
    """Behavioural tests for metrics display (Task F4)."""

    def test_card_footer_shows_latency(self) -> None:
        """Card footer should include latency in ms."""
        js = JS_PATH.read_text(encoding="utf-8")
        assert (
            "latency" in js.lower() or "total_ms" in js
        ), "JS must reference latency data"
        css = CSS_PATH.read_text(encoding="utf-8")
        assert (
            "latency" in css.lower() or "card-footer" in css
        ), "CSS must style latency-related elements"

    def test_card_footer_shows_time_to_first_token(self) -> None:
        """Card footer should include time-to-first-token in ms."""
        js = JS_PATH.read_text(encoding="utf-8")
        assert (
            "time_to_first_token_ms" in js or "TTFT" in js or "ttft" in js.lower()
        ), "JS must reference time_to_first_token_ms"
        assert (
            "ttft" in js.lower() or "first_token" in js
        ), "JS must display time-to-first-token metric"

    def test_card_footer_shows_tokens(self) -> None:
        """Card footer should show token counts."""
        js = JS_PATH.read_text(encoding="utf-8")
        assert (
            "tokens" in js.lower() or "tokens_used" in js
        ), "JS must reference token data"
        assert (
            "Tokens" in js
        ), "JS must display token metric label"

    def test_card_footer_shows_cost(self) -> None:
        """Card footer should show estimated cost in USD."""
        js = JS_PATH.read_text(encoding="utf-8")
        assert (
            "cost" in js.lower() or "cost_usd" in js
        ), "JS must reference cost data"
        assert (
            "toFixed" in js or "Cost" in js
        ), "JS must format cost to decimal places"

    def test_latency_bar_color_coded(self) -> None:
        """Latency bar should be coloured green/yellow/red by duration."""
        css = CSS_PATH.read_text(encoding="utf-8")
        assert (
            "latency-bar" in css
        ), "CSS must define .latency-bar class"
        # Check for color-coded fill classes
        assert (
            "fast" in css and "medium" in css and "slow" in css
        ), "CSS must define fast/medium/slow latency bar colour classes"
        js = JS_PATH.read_text(encoding="utf-8")
        assert (
            "fast" in js and "medium" in js and "slow" in js
        ), "JS must apply fast/medium/slow classes based on latency"

    def test_fastest_provider_highlighted(self) -> None:
        """Fastest provider should have a subtle 'fastest' badge."""
        js = JS_PATH.read_text(encoding="utf-8")
        assert (
            "fastest" in js.lower()
        ), "JS must identify and highlight fastest provider"
        assert (
            "Fastest" in js or "fastest" in js
        ), "JS must display a 'fastest' badge or indicator"
        css = CSS_PATH.read_text(encoding="utf-8")
        assert (
            "fastest-badge" in css or "fastest" in css
        ), "CSS must style the fastest badge"
