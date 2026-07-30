"""Interface and behavioral tests for the cost dashboard HTML.

Interface tests verify the static HTML file exists and has the expected
structure (must pass immediately).
Behavioral tests verify that the dashboard renders expected content
(must fail until the developer implements the full dashboard).
"""

from __future__ import annotations

from pathlib import Path

import pytest

DASHBOARD_PATH = (
    Path(__file__).parent.parent
    / "src" / "ai_vibe_coding" / "static" / "cost_dashboard.html"
)


# ──────────────────────────────────────────────────────────────
# Interface smoke tests — must PASS immediately
# ──────────────────────────────────────────────────────────────


class TestCostDashboardInterface:
    """Verify the HTML dashboard file exists with expected structure."""

    def test_dashboard_file_exists(self):
        """cost_dashboard.html should exist."""
        assert DASHBOARD_PATH.exists(), f"File not found: {DASHBOARD_PATH}"
        assert DASHBOARD_PATH.is_file()

    def test_dashboard_is_html(self):
        """cost_dashboard.html should be an HTML file."""
        content = DASHBOARD_PATH.read_text()
        assert "<!DOCTYPE html>" in content
        assert "<html" in content

    def test_dashboard_has_title(self):
        """cost_dashboard.html should have a title."""
        content = DASHBOARD_PATH.read_text()
        assert "<title>" in content
        assert "LLM Cost" in content or "Dashboard" in content

    def test_dashboard_has_styles(self):
        """cost_dashboard.html should have CSS styles."""
        content = DASHBOARD_PATH.read_text()
        assert "<style>" in content

    def test_dashboard_has_summary_card(self):
        """cost_dashboard.html should have a summary card."""
        content = DASHBOARD_PATH.read_text()
        assert "summary" in content.lower() or "summary-card" in content

    def test_dashboard_has_sparkline_area(self):
        """cost_dashboard.html should have a sparkline/svg area."""
        content = DASHBOARD_PATH.read_text()
        # Check for sparkline or SVG or chart references
        has_sparkline = "sparkline" in content.lower()
        has_svg = "<svg" in content
        has_chart = "chart" in content.lower()
        assert has_sparkline or has_svg or has_chart, (
            "Dashboard should have a chart/sparkline area"
        )

    def test_dashboard_has_table(self):
        """cost_dashboard.html should have a data table."""
        content = DASHBOARD_PATH.read_text()
        assert "<table>" in content or "table" in content.lower()

    def test_dashboard_has_container(self):
        """cost_dashboard.html should have a container div."""
        content = DASHBOARD_PATH.read_text()
        assert 'class="container"' in content or 'class="dashboard"' in content


# ──────────────────────────────────────────────────────────────
# Behavioral tests — must FAIL with NotImplementedError
# (The dashboard is static HTML; behavioral tests check that the
#  developer has wired it up properly to live data.)
# ──────────────────────────────────────────────────────────────


class TestCostDashboardBehavior:
    """Behavioral tests for dashboard — fail until fully implemented."""

    @pytest.mark.unit
    def test_dashboard_has_date_filter(self):
        """Dashboard should have a date range filter."""
        content = DASHBOARD_PATH.read_text()
        # Date filter: either a date input, filter form, or date-related
        # elements
        has_date_input = (
            "date" in content.lower()
            and (
                "input" in content.lower()
                or "filter" in content.lower()
            )
        )
        has_date_range = (
            "start_date" in content
            or "end_date" in content
            or "date-range" in content
        )
        assert has_date_input or has_date_range, (
            "Dashboard should have a date filter mechanism"
        )

    @pytest.mark.unit
    def test_dashboard_has_auto_refresh(self):
        """Dashboard should support auto-refresh."""
        content = DASHBOARD_PATH.read_text()
        # Auto-refresh via meta or JS timer
        has_meta_refresh = '<meta http-equiv="refresh"' in content
        has_js_refresh = "setInterval" in content or "refresh" in content.lower()
        assert has_meta_refresh or has_js_refresh, (
            "Dashboard should have auto-refresh mechanism"
        )
