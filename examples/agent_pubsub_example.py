"""Event-driven monitoring pipeline with pub/sub agents.

Demonstrates AgentPubSubCoordinator with sensor, analyzer, alerter,
and reporter agents communicating via MessageBus topics.

Run:
    python -m examples.agent_pubsub_example
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from ai_vibe_coding.agent_templates import (
    AgentMessage,
    AgentPubSubCoordinator,
    MessageBus,
)


@dataclass
class Event:
    """Simulated system event."""
    level: str
    source: str
    message: str


def main() -> None:
    """Run the pub/sub monitoring pipeline."""
    bus = MessageBus()
    coordinator = AgentPubSubCoordinator(message_bus=bus)

    # ── 1. Register agents with subscriptions ───────────────────
    sensor_events: list[AgentMessage] = []
    analyzer_events: list[AgentMessage] = []
    alert_events: list[AgentMessage] = []
    report_data: list[str] = []

    def sensor_handler(msg: AgentMessage) -> None:
        sensor_events.append(msg)
        bus.publish(
            AgentMessage(
                from_agent="sensor",
                to_agent=None,
                type="log.info",
                payload=msg.payload,
            )
        )

    def analyzer_handler(msg: AgentMessage) -> None:
        analyzer_events.append(msg)
        # Detect anomalies and publish alerts
        if msg.payload.get("value", 0) > 80:
            bus.publish(
                AgentMessage(
                    from_agent="analyzer",
                    to_agent=None,
                    type="alert.critical",
                    payload={
                        "source": msg.payload.get("source", "unknown"),
                        "value": msg.payload.get("value", 0),
                    },
                )
            )

    def alerter_handler(msg: AgentMessage) -> None:
        alert_events.append(msg)
        report_data.append(f"ALERT: {msg.payload}")

    def reporter_handler(msg: AgentMessage) -> None:
        report_data.append(f"Report generated: {msg.payload}")

    coordinator.register_agent(
        "sensor", sensor_handler, subscription="sensor.*",
    )
    coordinator.register_agent(
        "analyzer", analyzer_handler, subscription="log.*",
    )
    coordinator.register_agent(
        "alerter", alerter_handler, subscription="alert.*",
    )
    coordinator.register_agent(
        "reporter", reporter_handler, subscription="report.*",
    )

    # ── 2. Start ────────────────────────────────────────────────
    coordinator.start()
    print("Monitoring pipeline started.\n")

    # ── 3. Simulate sensor events ───────────────────────────────
    for i in range(5):
        msg = AgentMessage(
            from_agent="sensor",
            to_agent=None,
            type="sensor.cpu",
            payload={"source": f"server-{i}", "value": 50 + i * 15},
        )
        bus.publish(msg)
        time.sleep(0.1)

    # ── 4. Stop ─────────────────────────────────────────────────
    coordinator.stop()

    print(f"Sensor events:   {len(sensor_events)}")
    print(f"Analyzer events: {len(analyzer_events)}")
    print(f"Alert events:    {len(alert_events)}")
    print(f"Report entries:  {len(report_data)}")


if __name__ == "__main__":
    main()
