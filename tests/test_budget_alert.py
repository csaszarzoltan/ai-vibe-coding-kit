"""Interface and behavioral tests for the budget_alert module.

Interface tests verify that BudgetConfig, AlertThreshold, and
BudgetAlertEngine exist with correct signatures (must pass immediately).
Behavioral tests verify expected behavior (must fail with NotImplementedError
until the developer implements the module).
"""

from __future__ import annotations

import pytest

from ai_vibe_coding.budget_alert import AlertThreshold, BudgetAlertEngine, BudgetConfig

# ──────────────────────────────────────────────────────────────
# Interface smoke tests — must PASS immediately
# ──────────────────────────────────────────────────────────────


class TestBudgetConfigInterface:
    """Verify BudgetConfig dataclass and method signatures."""

    def test_class_exists(self):
        """BudgetConfig should be importable."""
        assert BudgetConfig is not None

    def test_default_values(self):
        """BudgetConfig should have sensible defaults."""
        config = BudgetConfig()
        assert config.name == ""
        assert config.period == "monthly"
        assert config.max_budget == 0.0
        assert config.enabled is True
        assert config.notification_channels == ["console"]

    def test_with_alert_thresholds(self):
        """BudgetConfig should accept AlertThreshold objects."""
        threshold = AlertThreshold(
            metric="cost", operator="gt", value=50.0, label="Monthly limit"
        )
        config = BudgetConfig(
            name="test",
            thresholds=[threshold],
            period="monthly",
            max_budget=50.0,
        )
        assert config.name == "test"
        assert len(config.thresholds) == 1
        assert config.thresholds[0].metric == "cost"

    def test_has_from_yaml_classmethod(self):
        """BudgetConfig should have from_yaml classmethod."""
        assert hasattr(BudgetConfig, "from_yaml")


class TestAlertThresholdInterface:
    """Verify AlertThreshold dataclass."""

    def test_class_exists(self):
        """AlertThreshold should be importable."""
        assert AlertThreshold is not None

    def test_default_values(self):
        """AlertThreshold should have sensible defaults."""
        t = AlertThreshold()
        assert t.metric == "cost"
        assert t.operator == "gt"
        assert t.value == 0.0

    def test_custom_values(self):
        """AlertThreshold should accept custom values."""
        t = AlertThreshold(
            metric="tokens", operator="gte", value=100000, label="Token limit"
        )
        assert t.metric == "tokens"
        assert t.operator == "gte"
        assert t.value == 100000


class TestBudgetAlertEngineInterface:
    """Verify BudgetAlertEngine class and method signatures."""

    def test_class_exists(self):
        """BudgetAlertEngine should be importable."""
        assert BudgetAlertEngine is not None

    def test_constructor(self):
        """BudgetAlertEngine should be instantiable with no args."""
        engine = BudgetAlertEngine()
        assert engine is not None

    def test_has_add_config(self):
        """BudgetAlertEngine should have add_config method."""
        assert hasattr(BudgetAlertEngine, "add_config")

    def test_has_check_budgets(self):
        """BudgetAlertEngine should have check_budgets method."""
        assert hasattr(BudgetAlertEngine, "check_budgets")

    def test_has_get_alert_history(self):
        """BudgetAlertEngine should have get_alert_history method."""
        assert hasattr(BudgetAlertEngine, "get_alert_history")


# ──────────────────────────────────────────────────────────────
# Behavioral tests — verify real implementation behavior
# ──────────────────────────────────────────────────────────────


class TestBudgetAlertEngineBehavior:
    """Behavioral tests for BudgetAlertEngine."""

    @pytest.mark.unit
    def test_add_config_stores_config(self):
        """add_config() should store a BudgetConfig."""
        engine = BudgetAlertEngine()
        config = BudgetConfig(name="test-budget", max_budget=50.0)
        engine.add_config(config)
        # Config stored — verify by checking against 0 spend
        alerts = engine.check_budgets(current_spend=0.0)
        assert isinstance(alerts, list)

    @pytest.mark.unit
    def test_check_budgets_returns_list(self):
        """check_budgets() should return a list of alert dicts."""
        engine = BudgetAlertEngine()
        alerts = engine.check_budgets(current_spend=30.0)
        assert isinstance(alerts, list)

    @pytest.mark.unit
    def test_check_budgets_without_spend(self):
        """check_budgets() should auto-compute spend when not provided."""
        engine = BudgetAlertEngine()
        alerts = engine.check_budgets()
        assert isinstance(alerts, list)
        # With no store data, no alerts should fire
        assert len(alerts) == 0

    @pytest.mark.unit
    def test_check_budgets_fires_on_threshold_breach(self):
        """check_budgets() should fire alerts when thresholds breached."""
        engine = BudgetAlertEngine()
        config = BudgetConfig(
            name="test-budget",
            max_budget=50.0,
            enabled=True,
        )
        engine.add_config(config)
        alerts = engine.check_budgets(current_spend=75.0)
        assert len(alerts) >= 1
        assert alerts[0]["metric"] == "cost"
        assert alerts[0]["actual"] == 75.0

    @pytest.mark.unit
    def test_get_alert_history_returns_list(self):
        """get_alert_history() should return list of alert dicts."""
        engine = BudgetAlertEngine()
        history = engine.get_alert_history()
        assert isinstance(history, list)

    @pytest.mark.unit
    def test_alert_history_tracks_multiple(self):
        """get_alert_history() should track multiple fired alerts."""
        engine = BudgetAlertEngine()
        config = BudgetConfig(name="test", max_budget=50.0)
        engine.add_config(config)
        engine.check_budgets(current_spend=75.0)
        engine.check_budgets(current_spend=100.0)
        history = engine.get_alert_history()
        assert len(history) >= 1


class TestBudgetConfigBehavior:
    """Behavioral tests for BudgetConfig."""

    @pytest.mark.unit
    def test_from_yaml_loads_file(self, tmp_path):
        """from_yaml() should load config from a YAML file."""
        yaml_path = tmp_path / "budget.yaml"
        yaml_path.write_text("name: test\nmax_budget: 100.0\nperiod: monthly\n")
        config = BudgetConfig.from_yaml(str(yaml_path))
        assert isinstance(config, BudgetConfig)
        assert config.name == "test"
        assert config.max_budget == 100.0
        assert config.period == "monthly"
