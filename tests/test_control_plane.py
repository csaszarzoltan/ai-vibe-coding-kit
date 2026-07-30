from pathlib import Path

import pytest

from ai_vibe_coding.control_plane import ControlPlane, PermissionDenied, render_console


def plane(tmp_path: Path) -> ControlPlane:
    return ControlPlane(tmp_path / "control.db")


def test_virtual_key_cannot_use_model_outside_policy(tmp_path: Path) -> None:
    cp = plane(tmp_path)
    cp.upsert_provider("openai", ["gpt-4o", "gpt-4o-mini"], enabled=True)
    key = cp.create_virtual_key("team-a", ["gpt-4o-mini"], 10.0)
    with pytest.raises(PermissionDenied, match="MODEL_NOT_ALLOWED"):
        cp.authorize(key, "gpt-4o", estimated_cost=0.1)


def test_trace_tree_links_retry_tool_and_cost_without_secrets(tmp_path: Path) -> None:
    cp = plane(tmp_path)
    trace = cp.start_trace(
        "team-a", "request", {"api_key": "secret", "prompt": "hello"}
    )
    cp.add_span(
        trace, "provider", "FAILED", 30, 0.01, {"authorization": "Bearer secret"}
    )
    cp.add_span(trace, "retry", "COMPLETE", 20, 0.02, {"attempt": 2})
    cp.add_span(trace, "tool", "COMPLETE", 10, 0.0, {"name": "search"})
    exported = cp.export_trace(trace)
    assert "retry" in exported and "tool" in exported and '"cost": 0.03' in exported
    assert "secret" not in exported and "[REDACTED]" in exported


def test_release_gate_blocks_metric_regression(tmp_path: Path) -> None:
    cp = plane(tmp_path)
    experiment = cp.create_experiment("prompt-v2", {"accuracy": 0.9, "latency_ms": 500})
    cp.record_score(experiment, "accuracy", 0.85)
    cp.record_score(experiment, "latency_ms", 450)
    result = cp.evaluate_gate(experiment)
    assert result["state"] == "FAILED"
    assert result["violations"] == ["accuracy"]


def test_security_scan_blocks_exfiltration_and_redacts_evidence(tmp_path: Path) -> None:
    cp = plane(tmp_path)
    scan = cp.start_security_scan("agent-1", ["prompt_injection", "tool_exfiltration"])
    cp.record_finding(scan, "tool_exfiltration", "HIGH", "token=abc123", blocking=True)
    report = cp.security_report(scan)
    assert report["state"] == "FAILED"
    assert "abc123" not in report["findings"][0]["evidence"]


def test_hard_budget_blocks_request_but_preserves_ledger(tmp_path: Path) -> None:
    cp = plane(tmp_path)
    key = cp.create_virtual_key("team-a", ["gpt-4o"], 1.0)
    cp.record_spend(key, 0.9, "run-1")
    with pytest.raises(PermissionDenied, match="BUDGET_EXCEEDED"):
        cp.authorize(key, "gpt-4o", estimated_cost=0.2)
    assert cp.budget_summary(key)["spent"] == 0.9


def test_resume_checkpoint_does_not_repeat_completed_tool(tmp_path: Path) -> None:
    cp = plane(tmp_path)
    run = cp.create_agent_run("workflow-1", ["research", "approval", "publish"])
    cp.complete_agent_step(run, "research", {"result": "done"})
    cp.request_agent_approval(run, "approval", "alice")
    cp.decide_agent_approval(run, "approval", "bob", approved=True)
    assert cp.resume_agent_run(run) == ["publish"]


def test_consoles_have_accessible_recovery_and_modern_navigation(
    tmp_path: Path,
) -> None:
    cp = plane(tmp_path)
    for page in ("providers", "traces", "evaluations", "security", "budgets", "agents"):
        html = render_console(page, cp)
        assert "Skip to content" in html
        assert 'aria-live="polite"' in html
        assert "Try again" in html
        assert "Command center" in html


def test_control_plane_routes_are_documented() -> None:
    from ai_vibe_coding.app import app

    paths = set(app.openapi()["paths"])
    assert "/control/{page}" in paths
    assert "/api/v1/providers/{provider_id}" in paths
    assert "/api/v1/virtual-keys" in paths
    assert "/api/v1/traces" in paths
    assert "/api/v1/experiments" in paths
    assert "/api/v1/security-scans" in paths
    assert "/api/v1/agent-runs" in paths
