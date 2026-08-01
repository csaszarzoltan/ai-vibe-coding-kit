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
