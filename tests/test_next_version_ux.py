from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_vibe_coding.playground import create_router

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'static' / 'index.html'
JS = ROOT / 'static' / 'playground.js'


def test_provider_readiness_endpoint_reports_all_providers(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'secret')
    app = FastAPI()
    app.include_router(create_router())
    response = TestClient(app).get('/api/playground/providers')
    assert response.status_code == 200
    data = response.json()
    assert len(data['providers']) == 9
    openai = next(item for item in data['providers'] if item['provider'] == 'openai')
    assert openai['configured'] is True
    assert openai['model']
    ollama = next(item for item in data['providers'] if item['provider'] == 'ollama')
    assert ollama['local'] is True


def test_playground_has_accessible_live_regions_and_history():
    html = HTML.read_text(encoding='utf-8')
    assert 'class="skip-link"' in html
    assert 'aria-live="polite"' in html
    assert 'role="alert"' in html
    assert 'id="recent-runs"' in html
    assert 'id="system-prompt-input"' in html
    assert 'id="sort-results"' in html


def test_playground_persists_preferences_and_recent_runs():
    js = JS.read_text(encoding='utf-8')
    assert 'localStorage' in js
    assert 'savePreferences' in js
    assert 'saveRecentRun' in js
    assert 'loadRecentRuns' in js
    assert 'playground:run-completed' in js


def test_provider_readiness_is_rendered_in_the_ui():
    html = HTML.read_text(encoding='utf-8')
    js = JS.read_text(encoding='utf-8')
    assert 'id="provider-readiness-summary"' in html
    assert 'loadProviderReadiness' in js
    assert "fetch('/api/playground/providers')" in js
    assert 'provider-status' in js
    assert 'setup-required' in js


def test_packaged_static_assets_are_declared():
    pyproject = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
    assert 'static/*.html' in pyproject
    assert 'static/*.js' in pyproject
    assert 'static/*.css' in pyproject


def test_provider_errors_include_actionable_recovery_metadata(monkeypatch):
    from ai_vibe_coding import playground

    class BrokenProvider:
        def __init__(self, **kwargs):
            pass

        def stream(self, messages):
            raise RuntimeError('401 invalid API key')

    monkeypatch.setitem(playground.PROVIDER_CLASSES, 'openai', BrokenProvider)
    result = playground._call_provider('openai', 'hello')
    assert result.error
    assert result.error_code == 'credential_error'
    assert 'API key' in result.recovery_action


def test_failed_result_cards_offer_scoped_retry():
    js = JS.read_text(encoding='utf-8')
    assert 'retryProvider' in js
    assert 'Retry provider' in js
    assert "providers: [provider]" in js
    assert 'retrying' in js


def test_error_categories_are_accessible_and_not_color_only():
    css = (ROOT / 'static' / 'playground.css').read_text(encoding='utf-8')
    js = JS.read_text(encoding='utf-8')
    assert 'recovery-action' in css
    assert 'error-code' in css
    assert 'Recovery:' in js


def test_comparison_export_controls_and_functions_exist():
    html = HTML.read_text(encoding='utf-8')
    js = JS.read_text(encoding='utf-8')
    assert 'id="export-markdown"' in html
    assert 'id="export-json"' in html
    assert 'exportComparison' in js
    assert 'buildMarkdownExport' in js
    assert 'downloadTextFile' in js


def test_exports_are_privacy_aware_and_include_decision_evidence():
    js = JS.read_text(encoding='utf-8')
    assert "delete safeResult.raw" in js
    assert "delete safeResult.api_key" in js
    assert 'systemPrompt' in js
    assert 'generatedAt' in js
    assert 'playground:comparison-exported' in js


def test_copy_helper_does_not_depend_on_ambient_event():
    js = JS.read_text(encoding='utf-8')
    assert 'function copyResponse(provider, model, content, trigger)' in js
    assert 'showCopiedTooltip(trigger)' in js
    assert 'event && event.target' not in js


def test_keyboard_shortcuts_and_help_are_available():
    html = HTML.read_text(encoding='utf-8')
    js = JS.read_text(encoding='utf-8')
    assert 'id="shortcut-help"' in html
    assert 'id="shortcut-help-toggle"' in html
    assert 'handleKeyboardShortcut' in js
    assert "event.key === 'Enter'" in js
    assert "event.key === '/'" in js
    assert "event.key === '?'" in js
    assert "event.key === 'Escape'" in js


def test_local_history_has_explicit_clear_control():
    html = HTML.read_text(encoding='utf-8')
    js = JS.read_text(encoding='utf-8')
    assert 'id="clear-history"' in html
    assert 'clearRecentRuns' in js
    assert 'localStorage.removeItem(PLAYGROUND_RUNS_KEY)' in js
    assert 'playground:history-cleared' in js


def test_shortcuts_avoid_hijacking_text_entry():
    js = JS.read_text(encoding='utf-8')
    assert 'isEditableTarget' in js
    assert "target.tagName === 'TEXTAREA'" in js
    assert "target.tagName === 'INPUT'" in js


def test_preferred_result_and_decision_note_controls_exist():
    html = HTML.read_text(encoding='utf-8')
    js = JS.read_text(encoding='utf-8')
    assert 'id="decision-note"' in html
    assert 'id="preferred-result-summary"' in html
    assert 'Mark preferred' in js
    assert 'selectPreferredResult' in js
    assert 'preferred-provider' in js


def test_exports_include_preferred_result_and_decision_note():
    js = JS.read_text(encoding='utf-8')
    assert 'preferredProvider' in js
    assert 'decisionNote' in js
    assert '## Decision' in js
    assert 'Preferred provider:' in js


def test_decision_state_is_local_and_privacy_minimal():
    js = JS.read_text(encoding='utf-8')
    assert 'PLAYGROUND_DECISION_KEY' in js
    assert 'saveDecisionState' in js
    assert 'loadDecisionState' in js
    assert 'playground:preferred-result-selected' in js
    assert 'provider: provider' in js


def test_comparison_summary_is_visible_and_accessible():
    html = HTML.read_text(encoding='utf-8')
    js = JS.read_text(encoding='utf-8')
    assert 'id="comparison-summary"' in html
    assert 'aria-live="polite"' in html
    assert 'renderComparisonSummary' in js
    assert 'Successful' in js
    assert 'Failed' in js
    assert 'Total cost' in js
    assert 'Total tokens' in js


def test_summary_distinguishes_fastest_and_lowest_cost():
    js = JS.read_text(encoding='utf-8')
    assert 'Lowest latency' in js
    assert 'Lowest cost' in js
    assert 'fastestProvider' in js
    assert 'cheapestProvider' in js
    assert "No provider is labeled 'best'" in js


def test_summary_handles_partial_and_empty_results():
    js = JS.read_text(encoding='utf-8')
    assert 'partial comparison' in js
    assert 'No comparison results yet' in js
    assert 'Number.isFinite' in js


def test_new_comparison_resets_stale_decision_state():
    js = JS.read_text(encoding='utf-8')
    assert 'resetDecisionStateForNewRun' in js
    assert 'preferredProvider = null' in js
    assert "decisionNote.value = ''" in js
    assert 'PLAYGROUND_DECISION_KEY' in js
    assert 'localStorage.removeItem(PLAYGROUND_DECISION_KEY)' in js


def test_recent_run_restores_full_comparison_configuration():
    js = JS.read_text(encoding='utf-8')
    assert 'systemPrompt: payload.system_prompt' in js
    assert "systemPrompt.value = run.systemPrompt || ''" in js
    assert 'createdAt' in js
    assert 'formatRecentRunTime' in js


def test_recent_run_accessibility_exposes_timestamp_and_provider_count():
    js = JS.read_text(encoding='utf-8')
    assert "button.setAttribute('aria-label'" in js
    assert 'providerCount' in js
    assert 'toLocaleString' in js


def test_prompt_length_is_bounded_by_api_contract():
    from pydantic import ValidationError
    from ai_vibe_coding.playground import PlaygroundCompareRequest, MAX_PROMPT_LENGTH

    assert MAX_PROMPT_LENGTH == 20000
    PlaygroundCompareRequest(prompt='x' * MAX_PROMPT_LENGTH)
    try:
        PlaygroundCompareRequest(prompt='x' * (MAX_PROMPT_LENGTH + 1))
    except ValidationError:
        pass
    else:
        raise AssertionError('oversized prompt must be rejected')


def test_prompt_counter_and_limit_feedback_exist():
    html = HTML.read_text(encoding='utf-8')
    js = JS.read_text(encoding='utf-8')
    assert 'id="prompt-character-count"' in html
    assert 'maxlength="20000"' in html
    assert 'updatePromptCharacterCount' in js
    assert 'PROMPT_MAX_LENGTH = 20000' in js
    assert 'characters remaining' in js


def test_prompt_validation_is_accessible_and_prevents_oversized_runs():
    html = HTML.read_text(encoding='utf-8')
    js = JS.read_text(encoding='utf-8')
    assert 'id="prompt-validation-message"' in html
    assert 'aria-describedby="prompt-character-count prompt-validation-message"' in html
    assert 'promptTooLong' in js
    assert "setAttribute('aria-invalid'" in js
    assert 'Prompt is too long' in js
