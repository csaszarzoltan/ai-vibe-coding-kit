"""Budget alert engine for LLM cost management.

Provides threshold-based alerting on cost and token usage with
YAML configuration support.

Public API:
    BudgetConfig — budget configuration dataclass
    AlertThreshold — single threshold definition
    BudgetAlertEngine — main alert evaluation engine
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AlertThreshold:
    """A single alert threshold definition.

    Attributes:
        metric: Metric to monitor ("cost", "tokens", or "latency").
        operator: Comparison operator ("gt", "gte", "lt", "lte").
        value: Threshold value to compare against.
        label: Human-readable label for this threshold.
    """

    metric: str = "cost"
    operator: str = "gt"
    value: float = 0.0
    label: str = ""


@dataclass
class BudgetConfig:
    """Budget configuration for cost/usage alerting.

    Attributes:
        name: Name of this budget configuration.
        thresholds: List of AlertThreshold objects.
        period: Billing period ("daily", "weekly", "monthly").
        max_budget: Maximum allowed cost for the period.
        notification_channels: List of channels ("console", "slack", "email").
        enabled: Whether this budget is active.
    """

    name: str = ""
    thresholds: list[AlertThreshold] = field(default_factory=list)
    period: str = "monthly"
    max_budget: float = 0.0
    notification_channels: list[str] = field(default_factory=lambda: ["console"])
    enabled: bool = True

    @classmethod
    def from_yaml(cls, path: str | Path) -> BudgetConfig:
        """Load budget configuration from a YAML file.

        Args:
            path: Path to YAML config file.

        Returns:
            BudgetConfig instance populated from the YAML file.
        """
        path = Path(path)
        with open(path) as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Invalid YAML config in {path}: expected a dict")

        thresholds: list[AlertThreshold] = []
        for t in data.get("thresholds", []):
            thresholds.append(
                AlertThreshold(
                    metric=t.get("metric", "cost"),
                    operator=t.get("operator", "gt"),
                    value=float(t.get("value", 0.0)),
                    label=t.get("label", ""),
                )
            )

        return cls(
            name=str(data.get("name", "")),
            thresholds=thresholds,
            period=str(data.get("period", "monthly")),
            max_budget=float(data.get("max_budget", 0.0)),
            notification_channels=list(data.get("notification_channels", ["console"])),
            enabled=bool(data.get("enabled", True)),
        )


class BudgetAlertEngine:
    """Evaluates budget thresholds and fires alerts.

    Manages multiple BudgetConfig instances and checks current spend
    against configured thresholds on demand.

    Example:
        engine = BudgetAlertEngine()
        engine.add_config(BudgetConfig(name="monthly-llm", max_budget=50.0))
        alerts = engine.check_budgets(current_spend=30.0)
    """

    def __init__(self) -> None:
        self._configs: list[BudgetConfig] = []
        self._alert_history: list[dict[str, Any]] = []

    def add_config(self, config: BudgetConfig) -> None:
        """Add a budget configuration to the engine."""
        self._configs.append(config)

    def check_budgets(
        self, current_spend: float | None = None
    ) -> list[dict[str, Any]]:
        """Check all budgets against current spend.

        Args:
            current_spend: Optional override for current spend.
                           If None, uses the store to auto-compute.

        Returns:
            List of alert dicts with keys: name, metric, actual, threshold,
            message, timestamp.
        """
        if current_spend is None:
            spend_metrics = self._get_current_spend()
        else:
            spend_metrics = {
                "total_cost": current_spend,
                "total_tokens": 0,
                "avg_latency": 0.0,
            }

        alerts: list[dict[str, Any]] = []
        for config in self._configs:
            if not config.enabled:
                continue

            # Check max_budget limit
            if config.max_budget > 0:
                actual_cost = spend_metrics.get("total_cost", 0.0)
                if actual_cost > config.max_budget:
                    threshold = AlertThreshold(
                        metric="cost",
                        operator="gt",
                        value=config.max_budget,
                        label=config.name,
                    )
                    alert = self._fire_alert(threshold, actual_cost)
                    alerts.append(alert)

            # Check each threshold
            for threshold in config.thresholds:
                actual = self._get_metric_value(
                    threshold.metric, spend_metrics
                )
                if self._is_breached(actual, threshold.operator, threshold.value):
                    alert = self._fire_alert(threshold, actual)
                    alerts.append(alert)

        return alerts

    def _get_current_spend(self) -> dict[str, float]:
        """Get current spend metrics from the cost store.

        Returns dict with keys: "total_cost", "total_tokens", "avg_latency".
        """
        # By default return zeros; a real implementation would
        # query the cost store
        return {"total_cost": 0.0, "total_tokens": 0, "avg_latency": 0.0}

    def _get_metric_value(
        self, metric: str, spend_metrics: dict[str, float]
    ) -> float:
        """Extract the relevant value from spend_metrics."""
        if metric == "cost":
            return spend_metrics.get("total_cost", 0.0)
        elif metric == "tokens":
            return float(spend_metrics.get("total_tokens", 0))
        elif metric == "latency":
            return spend_metrics.get("avg_latency", 0.0)
        else:
            return 0.0

    def _is_breached(self, actual: float, operator: str, threshold: float) -> bool:
        """Check if a threshold is breached given the operator."""
        ops = {
            "gt": lambda a, t: a > t,
            "gte": lambda a, t: a >= t,
            "lt": lambda a, t: a < t,
            "lte": lambda a, t: a <= t,
        }
        handler = ops.get(operator)
        if handler is None:
            return False
        return handler(actual, threshold)

    def _fire_alert(
        self, threshold: AlertThreshold, actual: float
    ) -> dict[str, Any]:
        """Format an alert dict for a breached threshold.

        Returns alert dict with keys: name, metric, actual, threshold,
        message, timestamp.
        """
        alert = {
            "name": threshold.label or threshold.metric,
            "metric": threshold.metric,
            "actual": actual,
            "threshold": threshold.value,
            "message": (
                f"{threshold.metric} threshold breached: "
                f"{actual:.4f} {threshold.operator} {threshold.value:.4f}"
            ),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._alert_history.append(alert)
        return alert

    def get_alert_history(self) -> list[dict[str, Any]]:
        """Get the history of fired alerts.

        Returns list of alert dicts in chronological order.
        """
        return list(self._alert_history)


__all__ = [
    "AlertThreshold",
    "BudgetAlertEngine",
    "BudgetConfig",
]
