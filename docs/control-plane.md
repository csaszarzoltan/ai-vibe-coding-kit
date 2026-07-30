# AI Engineering Control Plane

## Architecture

```text
FastAPI / server-rendered console
    -> control API schemas
        -> ControlPlane application/domain service
            -> transactional SQLite repository
                -> existing provider, resilience, benchmark, agent, and MCP code
```

`ControlPlane` owns state transitions, policy enforcement, redaction, idempotency, and persistence. `control_api` owns HTTP validation and error mapping. The existing provider SDK and agent primitives remain backwards compatible and do not depend on the UI.

## Data and states

- Providers: `ACTIVE`, `DISABLED`.
- Traces and spans: `OPEN`, `COMPLETE`, `PARTIAL`, `FAILED`.
- Experiments: `RUNNING`, `PASSED`, `FAILED`.
- Security scans: `SCANNING`, `FAILED`; a future worker may close non-blocking scans as `PASSED`.
- Agent runs: `RUNNING`, `WAITING_APPROVAL`, `PAUSED`, `COMPLETED`, `FAILED`.
- Agent checkpoints: `COMPLETED`, `WAITING_APPROVAL`, `APPROVED`, `REJECTED`.

## Security boundary

Virtual-key plaintext is never persisted. Model scope and projected spend are checked before execution. Trace and finding payloads redact common secret fields and bearer tokens. Approval requesters cannot approve their own step. Production deployments must provide authenticated actor and tenant context at the HTTP boundary; the core service is designed to receive that context but the repository ships in single-instance local mode.

## Recovery

Spend writes deduplicate on the caller's run ID. Trace creation can use `Idempotency-Key`. Agent resume derives pending steps from persisted checkpoints, so completed tools are not repeated. Failed trace spans preserve successful sibling spans and mark the trace partial.

## Compatibility and migration

The feature is additive. Existing SDK, CLI, MCP, playground, and provider APIs are unchanged. SQLite tables use `CREATE TABLE IF NOT EXISTS`, allowing 0.10 installations to start 0.11 without a destructive rewrite. Rollback consists of disabling the control routes and retaining the additive database for later export or deletion.
