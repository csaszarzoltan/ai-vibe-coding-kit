# Product Analysis and Next-Version Software Requirements

**Product:** AI Vibe Coding Kit  
**Source reviewed:** `ZipPrompt.md` interpreted as a ZIP archive  
**Review basis:** Project structure, Python source, static HTML/CSS/JavaScript, API contracts, tests, documentation, examples, deployment files, changelog, and package configuration  
**Analysis date:** 2026-08-01

## Executive summary

The application has evolved from a Python SDK for multi-provider LLM access into a broader AI engineering platform. It now combines a developer library, benchmark and cost CLIs, an MCP tool server, a lightweight LLM comparison playground, a cost dashboard, and a six-workspace control plane for providers, traces, evaluations, security, budgets, and agent runs.

The product's strongest assets are its broad engineering capabilities, security-minded domain logic, extensive automated tests, and clear observability primitives. Its main product weakness is fragmentation. Capabilities are exposed through several disconnected surfaces, while the user-facing web experiences remain thinner than the backend. Users must translate technical concepts, IDs, configuration files, and API states into their own workflow. The next version should therefore prioritize a coherent operational journey, not more isolated backend modules.

The most valuable next release is a workflow-centered console that connects setup, experimentation, comparison, policy, monitoring, and remediation. Immediate priorities are unified navigation, guided onboarding, persistent playground runs, richer comparison controls, actionable trace/error drill-down, usable cost filtering, safe approval workflows, and clear system status. These changes reduce repeated setup, context switching, cognitive load, and uncertainty in daily work.

---

## 1. Product understanding

### What the application appears to do

**Observed:** The repository is a modular Python 3.11+ application with a FastAPI backend, static web frontends, CLI tools, reusable Python APIs, MCP integrations, SQLite persistence, tests, examples, documentation, and deployment templates.

Its product scope includes:

1. **Multi-provider LLM access:** A common client abstraction for OpenAI, Anthropic, DeepSeek, OpenRouter, MiMo, Gemini, Mistral, Cohere, and Ollama.
2. **Prompt experimentation:** A web playground that sends one prompt to selected providers and displays response content, model, latency, time to first token, tokens, cost, and errors.
3. **Cost and performance analysis:** In-memory and SQLite tracking, cost reports, budget alerts, provider/model comparison, task-profile recommendations, and a cost dashboard.
4. **AI engineering governance:** A control plane for provider policy, scoped virtual keys, budgets, traces, evaluations, security scans, and checkpointed agent approvals.
5. **Workflow orchestration:** Sequential, conditional, parallel, map-reduce, tool-using, human-in-the-loop, supervisor, and pub/sub patterns.
6. **Reliability operations:** Circuit breakers, retries, fallback chains, health checks, caching, rate limiting, quotas, chaos engineering, drift detection, regression testing, cost anomalies, and SLA checks.
7. **Developer integration:** MCP server tooling, Cursor and Claude Desktop configuration, Python examples, CI workflows, and benchmark CLI commands.

**Inference:** The product is becoming an AI engineering control and experimentation platform rather than remaining only a coding kit. Its most coherent market position is: **a local-first, provider-neutral environment for building, comparing, governing, and operating LLM and agent workloads.**

### Likely users

#### Primary segment: AI application developers

Goals:
- Connect providers quickly.
- Test the same prompt across models.
- compare output, speed, and cost.
- integrate selected models into Python applications.
- debug failed calls and tool executions.

#### Primary segment: AI/platform engineers

Goals:
- Standardize provider access.
- manage keys, model scopes, budgets, quotas, and failover.
- inspect traces and operational health.
- enforce security and release gates.
- integrate with CI/CD and MCP clients.

#### Secondary segment: QA and evaluation engineers

Goals:
- define repeatable benchmark and regression suites.
- compare candidate models and prompts.
- inspect metric deltas and failure cases.
- enforce pass/fail thresholds before release.

#### Secondary segment: FinOps, engineering managers, and team leads

Goals:
- see spend and usage by provider, model, user, session, or workload.
- identify anomalies and expensive patterns.
- set budgets and receive actionable alerts.
- balance quality, latency, and cost.

#### Secondary segment: Security and governance reviewers

Goals:
- inspect security findings and traces.
- verify secret redaction and policy enforcement.
- approve or reject sensitive agent actions.
- retain audit evidence.

### Main workflows and usage scenarios

#### Workflow A: Compare providers in the playground

1. Open the LLM Playground.
2. Select one or more providers from nine checkboxes.
3. Enter a prompt.
4. Run **Compare**.
5. Wait while all selected providers execute.
6. Review result cards sorted by total latency.
7. Compare content, total latency, time to first token, tokens, and cost.
8. Copy individual responses.

**Observed behavior:** The form prevents execution until prompt text and at least one provider are present. The UI supports Select All and Clear All, loading state, general error banner, per-provider error cards, a fastest badge, responsive layout, dark mode, and reduced-motion styling.

#### Workflow B: Analyze cost and latency

1. Open the cost dashboard.
2. Select a start and end date.
3. Review summary, sparkline, bar chart, and data table.
4. Wait for periodic page refresh.

**Observed limitation:** The date filter function logs values but does not implement filtering. The dashboard refreshes the whole page every 30 seconds and also includes a five-minute meta refresh. There is no visible loading/error/no-data design, grouping control, export action, or drill-down.

#### Workflow C: Operate through the control plane

1. Navigate to one of six workspaces: Providers, Traces, Evaluations, Security, Budgets, or Agents.
2. Perform create/update actions through versioned API contracts.
3. Inspect lifecycle states and recovery guidance.
4. Approve or reject checkpointed agent actions where applicable.

**Observed:** Backend domain logic supports provider/model policies, one-time virtual keys, preflight authorization, trace ingestion/export, evaluation gates, security scans, budgets, and agent runs. The control surfaces are server-rendered, responsive, keyboard-aware, dark-mode capable, and include status communication and recovery guidance.

**Inference:** The workspaces represent backend capabilities more clearly than end-to-end user journeys. A user investigating a failed or expensive agent run may need to move among Agents, Traces, Security, and Budgets manually without a shared run context.

#### Workflow D: Benchmark and select a model

1. Define tasks in JSON.
2. Run `ai-vibe-bench` against provider/model pairs.
3. choose repetitions and output format.
4. inspect accuracy, latency, cost, and error rate.
5. use cost compare/recommend commands for provider selection.
6. export Markdown, JSON, or console reports.

**Observed:** This workflow is capable but CLI-first. The web playground does not expose benchmark datasets, repeated runs, evaluators, confidence, or saved experiments.

#### Workflow E: Configure MCP integration

1. Install dependencies.
2. run the standalone MCP server.
3. configure Cursor or Claude Desktop using JSON.
4. restart the client.
5. verify read/write/list/search/execute/weather tools.

**Observed:** The workflow is documented and security-aware, but path configuration, client restart, and manual troubleshooting remain user burdens.

#### Workflow F: Program and operate agents/chains

1. Compose Python callables or agent configurations.
2. select sequential, conditional, parallel, supervisor, pub/sub, tool-use, or HITL patterns.
3. run the workflow.
4. inspect outputs, statuses, costs, tokens, latency, and delegation traces.
5. handle errors or approvals programmatically.

**Inference:** This is powerful for developers, but users have no visual authoring, dry-run preview, replay, or stepwise debugging surface.

---

## 2. UI/UX analysis

### Strengths

1. **Simple core playground flow.** Provider selection, prompt entry, Compare, and result cards create a learnable first-use path.
2. **Useful result metrics.** Total latency, time to first token, token usage, cost, provider, and model are visible next to output.
3. **Partial failure isolation.** A failed provider can appear as an error card while other provider results remain useful.
4. **Responsive baseline.** The playground uses mobile-first grid behavior and the control plane is designed for responsive layouts.
5. **Dark-mode awareness.** CSS respects system color scheme.
6. **Immediate input prevention.** The Compare button is disabled until minimum conditions are satisfied, reducing avoidable API calls.
7. **Bulk provider controls.** Select All and Clear All help users avoid nine repetitive checkbox actions.
8. **Security is reflected in workflows.** Model scope, projected spend, secret redaction, approval separation, path sandboxing, and SSRF protection reduce high-risk errors.
9. **Operational state vocabulary.** Explicit states for traces, experiments, scans, agents, and checkpoints provide a foundation for understandable UI feedback.
10. **Broad automated contract coverage.** Tests document expected frontend elements, API behavior, security rules, state transitions, and accessibility hooks.

### Weaknesses

1. **Fragmented product surfaces.** Playground, cost dashboard, control plane, CLI, MCP setup, and Python orchestration do not read as one product journey.
2. **Feature-centric navigation.** Workspaces are organized by system objects rather than common goals such as “compare a change,” “investigate a failed run,” or “reduce spend.”
3. **No persistent experiment history in the playground.** Results are transient. Users cannot reopen, duplicate, tag, compare, or share a previous run.
4. **Provider selection lacks context.** Checkboxes show provider names only. They do not show configured status, selected model, pricing tier, health, expected latency, key availability, or policy restrictions.
5. **Comparison is visually shallow.** Cards are sorted by latency, which can bias attention toward speed even when users care about quality, cost, or compliance.
6. **No quality evaluation.** Users must read multiple outputs manually. There is no side-by-side diff, rating rubric, preferred response selection, evaluator score, or annotation.
7. **Limited run controls.** The playground exposes no model, temperature, max tokens, system prompt, seed, timeout, streaming, tool-use, or task profile controls.
8. **Long responses are hard to scan.** Plain-text bodies do not provide Markdown rendering, code highlighting, collapse/expand, synchronized scrolling, or content diffing.
9. **Error recovery is under-specified.** Error text is shown, but the UI does not consistently map errors to next actions such as configure key, retry provider, change model, or inspect trace.
10. **The cost dashboard is not functionally complete.** Its filter is a placeholder, refresh is disruptive, and charts lack interaction.
11. **Inconsistent information architecture.** There is no obvious shared navigation, breadcrumb, global search, environment/tenant selector, or cross-linking among related system objects.
12. **Terminology is expert-heavy.** Terms such as TTFT, preflight, virtual key, span, gate, drift, and checkpoint need contextual help for less-experienced users.
13. **Configuration depends on manual files/environment variables.** This is appropriate for advanced users but creates setup friction and hidden failure states.
14. **Accessibility is uneven.** The control plane mentions skip navigation and live status, but the playground HTML lacks an explicit skip link and the static error banner lacks an explicit `role="alert"` or `aria-live` in the observed markup.
15. **Copy interaction is fragile.** The JavaScript uses an ambient `event` reference when showing copy feedback. That may be unavailable in some browsers and does not establish a robust focus/status pattern.

### Confusing elements

- **“Select All” can trigger high cost** without a projected spend preview or warning.
- **The fastest badge can be interpreted as “best.”** It measures only total latency.
- **Model identity is reported after execution but not chosen before execution.** Users may not know which model a provider will use.
- **Two refresh mechanisms on the cost dashboard** suggest unclear refresh behavior.
- **Version cues appear inconsistent.** Repository changelog shows version 0.11.0 while one app test expects the FastAPI application version to be 0.3.0. This can reduce trust during troubleshooting.
- **Documentation and runtime terminology may drift.** Some guides describe intended capabilities while code/tests include older names or staged implementation language.

### Friction points

1. Re-selecting the same providers for every comparison.
2. Re-entering recurring prompts and parameters.
3. Manually scanning many outputs for differences.
4. Losing results after navigation or refresh.
5. Copying results one card at a time.
6. Switching to CLI for repeat runs, datasets, and report generation.
7. Switching to separate pages to connect spend, trace, security, and agent context.
8. Diagnosing missing API keys or unhealthy providers only after a failed run.
9. Manually editing MCP paths and restarting clients.
10. Waiting for all providers before seeing any result, despite some providers finishing sooner.
11. Full-page dashboard refresh interrupting reading and keyboard position.
12. Entering object IDs to find related operational records, if the console exposes backend objects directly.

### Navigation and workflow observations

A stronger navigation model would combine:

- **Build:** Playground, Workflows, MCP/Tools
- **Evaluate:** Comparisons, Benchmarks, Experiments
- **Operate:** Runs, Traces, Health
- **Govern:** Providers, Keys, Budgets, Security, Approvals
- **Analyze:** Cost, Latency, Quality, Usage

Every run should become a first-class object with links to its prompt/configuration, provider attempts, output, metrics, trace, spend, security findings, and agent checkpoints. This would replace page-to-page reconstruction with a single user-centered investigation flow.

---

## 3. User behavior analysis

### Likely user habits

**Inference based on the interfaces and domain:**

1. Users will repeatedly compare a stable shortlist of two to four provider/model combinations rather than all nine.
2. Users will reuse prompts, system instructions, and parameter presets for regression testing.
3. Users will first scan whether a run succeeded, then read output, then inspect latency/cost if deciding between viable responses.
4. Users will copy the preferred answer into code, an issue, a document, or another tool.
5. Platform users will investigate outliers, not aggregate averages alone. They need to move from daily spend to a provider/model/run.
6. Evaluation users will iterate: modify prompt, rerun, compare with baseline, annotate, and decide whether to promote.
7. Agent operators will monitor exceptions, approval queues, blocked tools, and expensive/slow steps more frequently than completed normal runs.
8. Administrators will prefer safe defaults and bulk policy operations over editing many objects individually.
9. Local/Ollama users will expect the UI to make privacy and zero marginal API cost visible.
10. Users will expect keyboard shortcuts for high-frequency actions after repeated use.

### Repeated actions

- Selecting the same providers.
- Entering the same model parameters.
- Retrying only failed providers.
- Copying or exporting responses.
- Opening traces after a failed comparison.
- Filtering cost by the same team/provider/date.
- Reviewing pending approvals.
- Switching between candidate and baseline experiments.
- Updating credentials and verifying connectivity.
- Running the same benchmark after a prompt or model change.

### Likely pain points

1. **Setup uncertainty:** Users cannot see readiness before running.
2. **Comparison fatigue:** Nine long responses exceed comfortable side-by-side reading.
3. **Decision ambiguity:** Speed and cost are measured, but quality requires manual judgment.
4. **No continuity:** Transient runs prevent iterative learning and collaboration.
5. **Context loss:** Separate operational pages force users to remember identifiers and reconstruct causality.
6. **Budget anxiety:** Broad provider selection can create unknown spend.
7. **Failure ambiguity:** Generic errors do not always distinguish credential, quota, policy, network, provider, timeout, or application failures.
8. **Operational overload:** Many advanced capabilities increase cognitive load without role-based views and progressive disclosure.
9. **Manual configuration:** Environment variables and JSON paths are error-prone, especially across operating systems.
10. **Incomplete analytics:** A non-functional date filter undermines confidence in dashboard accuracy.

### Usage bottlenecks

- Waiting for all providers instead of progressively rendering completed results.
- Reading unformatted long outputs.
- Comparing only one run at a time.
- Repeating configuration rather than using presets.
- Moving from aggregate metrics to root cause without direct drill-down.
- Running benchmarks in CLI and then manually sharing reports.
- Managing approval queues without prioritization by risk, age, or cost impact.

### Expected but missing interactions

- Save, duplicate, rename, tag, and share a comparison.
- Favorite provider/model sets.
- Choose model and parameters per provider.
- Show provider readiness and health before execution.
- Estimate maximum/projected cost before running.
- Stream each result card independently.
- Cancel a whole run or one provider.
- Retry only failed providers.
- Rank by cost, latency, quality score, or custom preference.
- Diff two responses or two runs.
- Rate, annotate, and mark a preferred output.
- Export full comparison as JSON, CSV, Markdown, or shareable link.
- Open the trace and spend record from a result card.
- Filter and drill down dashboard data without page reload.
- View empty, loading, partial, stale, and error states consistently.
- Receive a clear next action for each error category.
- Use keyboard shortcuts such as run, cancel, next result, and copy.

---

## 4. What should be improved

### Critical improvements

1. **Unify the product shell and navigation.** Connect the playground, runs, evaluations, traces, cost, security, budgets, providers, and agents.
2. **Create persistent run history.** Store comparisons and their full configuration, outputs, metrics, errors, trace IDs, costs, and timestamps.
3. **Add provider readiness and model configuration.** Show configured/unconfigured, health, key/policy status, selected model, and estimated cost before execution.
4. **Implement progressive, cancellable comparison.** Render results as providers complete and allow per-provider retry/cancel.
5. **Make cost analytics functional and drillable.** Implement filtering, grouping, no-data/error states, and links to underlying runs.
6. **Provide actionable error recovery.** Normalize error categories and attach recommended actions.
7. **Link operational context.** A run detail view should connect to trace, security, budget, evaluation, and agent steps.
8. **Strengthen playground accessibility.** Add skip navigation, explicit live regions, keyboard operation, focus management, accessible loading state, and non-color status cues.
9. **Resolve version and documentation consistency.** Display one build/version identity and clearly separate implemented, experimental, and planned features.
10. **Add explicit safety confirmation for high-cost or sensitive runs.** Use projected cost, tool risk, data scope, and policy state.

### Medium-priority improvements

1. Saved provider/model/parameter presets.
2. System prompt and common generation parameters.
3. Side-by-side response diff and synchronized scrolling.
4. Markdown and code rendering with safe sanitization.
5. User ratings, annotations, and preferred-answer selection.
6. Browser-based benchmark creation and saved evaluation suites.
7. Role-based landing pages and permission-aware navigation.
8. Global search across runs, traces, experiments, providers, and agent runs.
9. Non-disruptive dashboard refresh with freshness indicator.
10. Guided credential and MCP setup with connection tests.
11. Bulk approval and policy actions with guarded confirmation.
12. Export/share options for comparisons, traces, and reports.

### Nice-to-have improvements

1. Visual workflow builder for chains and agents.
2. Replay a trace from a selected step with modified parameters.
3. Organization-specific quality rubrics and weighted rankings.
4. Cost forecasting based on sampled workload volume.
5. Notifications for approval queues, anomalies, and completed long runs.
6. Prompt library with ownership, change history, and usage signals.
7. Command palette and customizable keyboard shortcuts.
8. Onboarding sample workspace with synthetic data.

---

## 5. Requirements

### Prioritization method

- **Must have:** Required to make core daily workflows coherent, trustworthy, accessible, and efficient.
- **Should have:** High-value improvements that deepen comparison, evaluation, and operations after the core flow is stable.
- **Could have:** Valuable extensions with lower immediate frequency or higher implementation cost.
- **Won't have for now:** Explicitly deferred to avoid expanding scope before the core product journey is usable.

### Business requirements

#### BR-01: Unified AI engineering workspace

- **Type:** Business
- **Description:** The product shall offer a single navigable web workspace connecting experimentation, evaluation, operations, and governance.
- **User value:** Users complete common journeys without guessing which separate surface or CLI to use.
- **Priority:** Must have
- **Rationale:** Existing capabilities are broad but fragmented across playground, dashboard, control plane, CLI, MCP, and Python APIs.
- **Acceptance criteria:**
  - A persistent primary navigation exposes Build, Evaluate, Operate, Govern, and Analyze areas.
  - Every current web workspace is reachable within two navigation actions from the home view.
  - Breadcrumbs and page titles identify the current area and object.
  - Permission-restricted sections are hidden or clearly disabled with an explanation.
  - Cross-links preserve tenant/environment and object context.

#### BR-02: Traceable model-selection decisions

- **Type:** Business
- **Description:** The product shall preserve the evidence behind provider, model, prompt, and release decisions.
- **User value:** Teams can explain why a model or prompt was selected and reproduce the comparison.
- **Priority:** Must have
- **Rationale:** The playground is transient while benchmark evidence is CLI/report based.
- **Acceptance criteria:**
  - Every comparison can be saved with immutable execution metadata.
  - A saved run records prompt, system prompt, parameters, provider/model, output, metrics, evaluator results, errors, and timestamps.
  - Users can mark a preferred candidate and record a decision note.
  - Saved runs can be reopened and duplicated.
  - Changes made in a duplicated run are visibly distinguished from the source.

#### BR-03: Cost-aware usage governance

- **Type:** Business
- **Description:** The system shall help users predict, monitor, and control LLM spend at run, project, tenant, and provider levels.
- **User value:** Teams avoid unexpected spend and can optimize usage without separate analysis.
- **Priority:** Must have
- **Rationale:** Cost tracking and budgets exist, but the playground does not show projected run cost and the cost dashboard is incomplete.
- **Acceptance criteria:**
  - The UI displays projected cost or a clearly labeled estimate range before execution.
  - Budget/policy blocks appear before calls are sent.
  - Actual cost is linked to the saved run and trace.
  - Users can filter and group spend by date, provider, model, project, session, and run.
  - Threshold alerts identify cause, impact, and recommended action.

#### BR-04: Operational trust and recoverability

- **Type:** Business
- **Description:** The product shall make failures diagnosable and recoverable without inspecting server logs for common cases.
- **User value:** Users restore work faster and trust system status.
- **Priority:** Must have
- **Rationale:** The backend has detailed states and recovery primitives, but user-facing errors are comparatively generic.
- **Acceptance criteria:**
  - User-visible failures are categorized as validation, credential, policy, quota, timeout, network, provider, security, or internal.
  - Each category includes a safe recommended next action.
  - Failed provider calls can be retried independently.
  - Run details link to relevant trace/span and configured provider.
  - Recovery actions do not repeat completed, billable steps unless the user explicitly requests replay.

### User requirements

#### UR-01: Save and reuse comparison setups

- **Type:** User
- **Description:** Users shall be able to save provider/model/parameter sets as named presets.
- **User value:** Frequent comparisons require fewer repetitive selections.
- **Priority:** Must have
- **Rationale:** Users are likely to reuse a short provider shortlist and stable parameters.
- **Acceptance criteria:**
  - Users can create, rename, update, duplicate, and delete personal presets.
  - Presets include provider, model, generation parameters, and optional system prompt.
  - The most recently used preset is offered on return without automatically starting a run.
  - Missing credentials or policy-invalid entries are flagged before execution.

#### UR-02: Progressive comparison feedback

- **Type:** User
- **Description:** Users shall see each provider result as soon as it completes.
- **User value:** Faster perceived performance and earlier inspection of available results.
- **Priority:** Must have
- **Rationale:** Current loading replaces the results area until the aggregate call completes.
- **Acceptance criteria:**
  - Each selected provider receives a pending card immediately.
  - Cards independently transition through queued, running, complete, failed, cancelled, or blocked.
  - Completed outputs remain available while other providers continue.
  - Users can cancel the full run or one provider.
  - Partial results remain saveable.

#### UR-03: Flexible ranking and comparison

- **Type:** User
- **Description:** Users shall be able to sort and compare results by the criterion relevant to their task.
- **User value:** “Best” is not conflated with “fastest.”
- **Priority:** Must have
- **Rationale:** Existing cards are automatically sorted by latency and only the fastest is highlighted.
- **Acceptance criteria:**
  - Sorting supports original order, latency, TTFT, cost, token count, quality score, and user rating.
  - The active sort and its direction are visible.
  - Badges use explicit labels such as “Lowest cost” or “Lowest latency.”
  - No unqualified “best” badge is shown without a defined rubric.

#### UR-04: Compare outputs efficiently

- **Type:** User
- **Description:** Users shall be able to compare two outputs or two runs with differences highlighted.
- **User value:** Reduces manual scanning and makes prompt/model changes easier to evaluate.
- **Priority:** Should have
- **Rationale:** Long plain-text cards create comparison fatigue.
- **Acceptance criteria:**
  - Users can choose any two successful outputs.
  - The diff supports inline and side-by-side modes.
  - Added, removed, and changed content is distinguishable without relying only on color.
  - Code blocks preserve formatting.
  - Users can return to the full comparison without losing selection.

#### UR-05: Resume work from history

- **Type:** User
- **Description:** Users shall be able to search, filter, and reopen previous runs.
- **User value:** Supports iterative work, audit, and collaboration.
- **Priority:** Must have
- **Rationale:** Current comparison state is not persistent.
- **Acceptance criteria:**
  - History supports search by prompt text, tag, provider, model, status, and date.
  - Users can reopen details, duplicate configuration, rerun failed providers, and export.
  - Results display creator, time, environment, and data freshness.
  - Deleted runs follow an explicit retention policy.

#### UR-06: Understand provider readiness before running

- **Type:** User
- **Description:** Users shall know whether each provider is configured, healthy, allowed, and within quota before selection.
- **User value:** Avoids preventable failed runs.
- **Priority:** Must have
- **Rationale:** Provider-only checkboxes hide key availability, health, model, and policy status.
- **Acceptance criteria:**
  - Each provider option displays readiness state and selected model.
  - Unavailable providers include a reason and setup or remediation link.
  - Stale health information shows its timestamp.
  - Users cannot accidentally select a policy-blocked model.
  - Local providers are clearly identified as local/private where applicable.

#### UR-07: Review approvals in context

- **Type:** User
- **Description:** Approvers shall see action, arguments, risk, requester, previous steps, projected cost, and policy findings before deciding.
- **User value:** Faster, safer approval decisions.
- **Priority:** Must have
- **Rationale:** The domain supports checkpoint approval and self-approval prevention; the UI must provide sufficient decision context.
- **Acceptance criteria:**
  - Approval detail includes run, step, tool, sanitized arguments, requester, age, risk reason, and projected impact.
  - Approve and reject require an audit note when policy requires it.
  - Requesters cannot approve their own step.
  - Decisions are immutable audit events.
  - The interface warns before bulk approval and excludes incompatible items.

### Functional requirements

#### FR-01: Persistent comparison run entity

- **Type:** Functional
- **Description:** The backend shall persist comparison runs and per-provider attempts.
- **User value:** Enables history, replay, audit, drill-down, and collaboration.
- **Priority:** Must have
- **Rationale:** This is the foundation for most high-value UX improvements.
- **Acceptance criteria:**
  - A run has ID, tenant/project, creator, prompt, system prompt, parameters, timestamps, status, estimates, actual totals, and optional source run ID.
  - Each provider attempt stores provider, model, status, output/error, token metrics, latency metrics, cost, trace/span IDs, and retry lineage.
  - Writes are idempotent for a client-supplied request key.
  - Partial completion is preserved.
  - API supports create, get, list/filter, duplicate, cancel, retry-attempt, and export.

#### FR-02: Provider configuration preflight

- **Type:** Functional
- **Description:** The system shall execute preflight validation before dispatching a run.
- **User value:** Prevents predictable failures and overspend.
- **Priority:** Must have
- **Rationale:** Existing control-plane preflight logic should be surfaced in the playground.
- **Acceptance criteria:**
  - Preflight checks credential presence, provider state, model scope, quota, budget, projected spend, and endpoint policy.
  - The API returns per-provider allowed/blocked results.
  - A blocked provider is not called.
  - Users may proceed with allowed providers after acknowledging partial execution.
  - Preflight results are logged without exposing secrets.

#### FR-03: Streaming and cancellation

- **Type:** Functional
- **Description:** The comparison API shall support incremental status/output events and cancellation.
- **User value:** Reduces wait time and gives control over cost.
- **Priority:** Must have
- **Rationale:** Streaming is a documented best practice and the application already supports streaming in parts of the SDK.
- **Acceptance criteria:**
  - Server emits attempt status and output events via an authenticated streaming mechanism.
  - Events contain run ID, attempt ID, sequence, type, and timestamp.
  - Reconnection resumes from the last acknowledged sequence where possible.
  - Cancellation is idempotent.
  - Cancelled attempts do not continue billing work that the application can safely stop.

#### FR-04: Per-attempt retry

- **Type:** Functional
- **Description:** Users shall be able to retry a failed provider attempt without rerunning successful providers.
- **User value:** Saves time and cost.
- **Priority:** Must have
- **Rationale:** Partial provider failure is already isolated in results.
- **Acceptance criteria:**
  - Retry creates a linked attempt with incremented attempt number.
  - Original output/error remains available.
  - Retry uses the original configuration unless the user explicitly edits it.
  - Budget and policy preflight runs again.
  - The UI identifies which attempt is current.

#### FR-05: Functional cost analytics filters

- **Type:** Functional
- **Description:** The cost dashboard shall query and render filtered analytics without a full-page reload.
- **User value:** Users can investigate cost efficiently.
- **Priority:** Must have
- **Rationale:** Current date filtering is a placeholder.
- **Acceptance criteria:**
  - Date range filtering validates start/end order and timezone.
  - Filters support provider, model, project/tenant, status, and run type.
  - Summary, trend, breakdown, and table update from the same applied filter set.
  - Filter state is encoded in the URL.
  - Users can drill from an aggregate row/chart point to matching runs.
  - Empty, loading, stale, and error states are explicit.

#### FR-06: Export and sharing

- **Type:** Functional
- **Description:** Users shall be able to export or share a complete comparison and analytics view.
- **User value:** Simplifies collaboration and decision records.
- **Priority:** Should have
- **Rationale:** Current copy works per card and CLI reports require a separate workflow.
- **Acceptance criteria:**
  - Comparison exports support Markdown, JSON, and CSV summary.
  - Secrets, raw keys, and redacted fields never appear.
  - Shared links are permission checked and can expire.
  - Export records prompt/configuration, outputs, metrics, errors, scores, and decision notes.
  - Users can copy a single clean response without provider metadata if desired.

#### FR-07: Evaluation on playground runs

- **Type:** Functional
- **Description:** Users shall be able to apply deterministic or configured evaluators to comparison outputs.
- **User value:** Adds quality evidence to cost and latency.
- **Priority:** Should have
- **Rationale:** Benchmark evaluators already exist but are disconnected from the playground.
- **Acceptance criteria:**
  - A run can optionally include expected answer and evaluator.
  - Supported initial evaluators include exact, contains, and fuzzy match.
  - Scores are stored per attempt with evaluator version.
  - The UI distinguishes machine score from human rating.
  - Evaluation failure does not discard provider output.

#### FR-08: Connection and setup wizard

- **Type:** Functional
- **Description:** The product shall provide guided provider and MCP setup with validation.
- **User value:** Reduces manual configuration and troubleshooting.
- **Priority:** Should have
- **Rationale:** Current environment-variable and JSON setup creates recurring path/key errors.
- **Acceptance criteria:**
  - The wizard lists supported providers and detects configured credentials without revealing them.
  - A connection test returns sanitized success/failure details.
  - MCP setup generates client-specific configuration and validates executable/path access.
  - OS-specific instructions are selected automatically where reliable.
  - Restart requirements are clearly stated and verifiable.

#### FR-09: Cross-object global search

- **Type:** Functional
- **Description:** Authorized users shall search runs, traces, experiments, findings, providers, and agent runs from one query interface.
- **User value:** Reduces navigation and identifier lookup.
- **Priority:** Should have
- **Rationale:** Related operational data currently spans multiple workspaces.
- **Acceptance criteria:**
  - Results are grouped by object type.
  - Search supports IDs, names, prompt text, tags, provider, and status.
  - Permission filtering occurs before results are returned.
  - Selecting a result opens its detail page with preserved search context.

#### FR-10: Unified run investigation view

- **Type:** Functional
- **Description:** The system shall provide one detail view for a comparison, benchmark, or agent run.
- **User value:** Enables root-cause analysis without manual cross-referencing.
- **Priority:** Must have
- **Rationale:** Run data, traces, costs, security, and approval states belong to one user task.
- **Acceptance criteria:**
  - Detail includes overview, configuration, attempts/steps, output, metrics, timeline, trace, cost, security, and approvals.
  - Related object IDs are clickable.
  - Failed/slow/expensive steps are visually prioritized.
  - The view supports deep links to a selected attempt/span/step.
  - Sensitive data follows redaction and permission policy.

### Non-functional requirements

#### NFR-01: Accessibility conformance

- **Type:** Non-functional
- **Description:** Core web workflows shall meet WCAG 2.2 AA.
- **User value:** Keyboard, screen-reader, low-vision, and motion-sensitive users can operate the product.
- **Priority:** Must have
- **Rationale:** Accessibility is partially addressed but uneven across surfaces.
- **Acceptance criteria:**
  - Automated accessibility tests run in CI for core pages.
  - All actions are keyboard operable with visible focus.
  - Status changes use appropriate live regions without excessive announcements.
  - Color is not the sole carrier of status or difference.
  - Text and interactive controls meet AA contrast.
  - Focus moves predictably after run, error, modal, and approval actions.

#### NFR-02: Performance and responsiveness

- **Type:** Non-functional
- **Description:** Common UI interactions shall remain responsive while long LLM operations run asynchronously.
- **User value:** The interface feels fast despite provider latency.
- **Priority:** Must have
- **Rationale:** Multi-provider calls can take seconds and should not block exploration.
- **Acceptance criteria:**
  - Initial application shell renders within 2.5 seconds at the agreed test profile.
  - Input and navigation remain interactive during active runs.
  - First provider status appears within 500 ms after run acceptance.
  - Completed provider results render within 250 ms after event receipt.
  - Large histories use pagination or virtualization.

#### NFR-03: Security and privacy

- **Type:** Non-functional
- **Description:** The product shall preserve existing fail-closed policies and prevent secret or sensitive-data exposure in UI, logs, exports, and events.
- **User value:** Teams can use the product without increasing credential and data leakage risk.
- **Priority:** Must have
- **Rationale:** The repository already treats redaction, scopes, SSRF, path access, and approvals as core trust boundaries.
- **Acceptance criteria:**
  - Raw virtual keys are displayed once and never persisted in plaintext.
  - Common secret fields and bearer tokens are redacted before persistence and display.
  - Authorization is enforced server-side by tenant and role.
  - Shared/exported artifacts reapply redaction.
  - Security-sensitive actions produce immutable audit records.
  - SSRF and path-sandbox tests remain in regression suites.

#### NFR-04: Reliability and idempotency

- **Type:** Non-functional
- **Description:** Repeated client requests and reconnects shall not duplicate spend, traces, or irreversible actions.
- **User value:** Users can safely retry after network interruption.
- **Priority:** Must have
- **Rationale:** Existing control-plane domain logic already uses idempotency and spend deduplication.
- **Acceptance criteria:**
  - Run creation, spend recording, trace ingestion, cancellation, and approval decisions accept idempotency controls.
  - Duplicate requests return the original result where applicable.
  - Completed agent steps are not repeated during resume.
  - Partial failures preserve successful sibling results.
  - Recovery behavior is covered by deterministic tests.

#### NFR-05: Observability and data freshness

- **Type:** Non-functional
- **Description:** User-facing data shall show freshness, source, and correlation IDs where operationally relevant.
- **User value:** Users know whether a status or metric is current and can escalate precisely.
- **Priority:** Should have
- **Rationale:** Auto-refresh and distributed provider calls can create stale or ambiguous displays.
- **Acceptance criteria:**
  - Dashboards show last-updated time and timezone.
  - Run and error views expose a safe correlation ID.
  - Stale data is labeled after a configurable threshold.
  - Client telemetry captures page/action failures without prompt or secret leakage.

#### NFR-06: Compatibility and migration

- **Type:** Non-functional
- **Description:** New web workflows shall remain additive to existing Python, CLI, MCP, and API integrations.
- **User value:** Existing adopters can upgrade without rewriting integrations.
- **Priority:** Must have
- **Rationale:** Backward compatibility is an explicit architectural goal.
- **Acceptance criteria:**
  - Existing public Python and CLI contracts remain functional or receive a documented deprecation window.
  - Database migrations are versioned and reversible when feasible.
  - API versioning remains under `/api/v1` or a documented successor.
  - Upgrade and rollback procedures are tested on representative 0.11 data.

### UX/UI requirements

#### UX-01: Goal-oriented home and navigation

- **Type:** UX/UI
- **Description:** The home experience shall present common goals and recent work rather than only subsystem names.
- **User value:** New and returning users find the next action quickly.
- **Priority:** Must have
- **Rationale:** Current architecture is capability-rich but system-centric.
- **Acceptance criteria:**
  - Home shows primary actions: Compare models, Run evaluation, Investigate failure, Review spend, Review approvals.
  - Recent runs and pending actions are visible based on role.
  - Navigation labels are consistent across all pages.
  - No core workflow requires memorizing a URL or object ID.

#### UX-02: Provider selector with progressive disclosure

- **Type:** UX/UI
- **Description:** Replace bare checkboxes with selectable provider rows/cards that expose essential readiness and model information.
- **User value:** Better choices with less trial-and-error.
- **Priority:** Must have
- **Rationale:** Provider names alone are insufficient for cost/health/policy decisions.
- **Acceptance criteria:**
  - Compact state shows provider, model, readiness, and rough cost tier.
  - Expanded state offers model and parameter selection.
  - Disabled options explain why and provide remediation.
  - Select All displays projected maximum/estimated cost and requires acknowledgement above a configurable threshold.

#### UX-03: Result-card readability

- **Type:** UX/UI
- **Description:** Result cards shall support readable formatted output and manageable long content.
- **User value:** Faster comprehension and copying.
- **Priority:** Must have
- **Rationale:** Plain text does not serve code-heavy LLM output well.
- **Acceptance criteria:**
  - Safe Markdown rendering supports headings, lists, links, tables, and code blocks.
  - Code blocks have syntax highlighting and copy controls.
  - Long responses can collapse/expand without losing scroll position.
  - Metrics remain visible in a consistent summary area.
  - Raw-text view is available.

#### UX-04: Consistent status and recovery patterns

- **Type:** UX/UI
- **Description:** All surfaces shall use a shared status language and action pattern.
- **User value:** Users learn one mental model for waiting, errors, blocks, and recovery.
- **Priority:** Must have
- **Rationale:** The codebase has many state systems and separate interfaces.
- **Acceptance criteria:**
  - A common component set covers loading, empty, success, warning, blocked, partial, cancelled, stale, and failed.
  - Status includes icon, text, optional timestamp, and next action.
  - Error messages identify what happened, what was preserved, and what the user can do.
  - Technical details are available through progressive disclosure.

#### UX-05: Keyboard efficiency

- **Type:** UX/UI
- **Description:** Frequent workflows shall support documented keyboard shortcuts.
- **User value:** Power users complete repeated comparisons faster.
- **Priority:** Should have
- **Rationale:** The target users are developer-heavy and repeat workflows frequently.
- **Acceptance criteria:**
  - Run, cancel, focus prompt, next/previous result, copy, and open command palette have shortcuts.
  - Shortcuts do not conflict with browser or assistive-technology conventions.
  - A discoverable shortcut help overlay exists.
  - All shortcut actions remain available through standard controls.

#### UX-06: Actionable cost dashboard

- **Type:** UX/UI
- **Description:** The cost dashboard shall support interactive exploration rather than passive auto-refresh.
- **User value:** Users move from anomaly to cause quickly.
- **Priority:** Must have
- **Rationale:** Current filtering is non-functional and reload behavior is disruptive.
- **Acceptance criteria:**
  - Filter controls show applied state and provide Reset.
  - Charts include accessible data table equivalents.
  - Hover/focus details show value, date, provider/model, and comparison period.
  - Clicking a chart segment filters the table and exposes matching runs.
  - Refresh updates data in place and shows last refresh time.

### Data and integration requirements

#### DIR-01: Canonical run, attempt, and correlation model

- **Type:** Data/Integration
- **Description:** The system shall define canonical identifiers and relationships across comparisons, benchmarks, traces, agent runs, spend, security findings, and approvals.
- **User value:** Reliable drill-down and cross-workspace context.
- **Priority:** Must have
- **Rationale:** The current subsystems have related but separate records.
- **Acceptance criteria:**
  - A documented schema defines run ID, attempt/step ID, trace ID, span ID, spend record ID, finding ID, and checkpoint ID relationships.
  - APIs return hyperlinks or relationship fields where authorized.
  - Correlation is preserved through retries, fallback, and replay.
  - Deletion/retention rules address linked records explicitly.

#### DIR-02: Pricing and model-catalog freshness

- **Type:** Data/Integration
- **Description:** Provider model and pricing data shall be versioned, timestamped, and visibly stale when not recently verified.
- **User value:** Cost estimates and model choices are trustworthy.
- **Priority:** Must have
- **Rationale:** Static pricing and model names can age quickly and directly affect decisions.
- **Acceptance criteria:**
  - Each catalog entry includes source/version, effective date, and last verified time.
  - Estimates state the pricing version used.
  - Administrators can update catalog data without code changes.
  - Invalid or unknown models fail clearly rather than silently using an unrelated default in user-facing flows.

#### DIR-03: Export interoperability

- **Type:** Data/Integration
- **Description:** Exports shall use stable schemas suitable for spreadsheets, BI, issue trackers, and CI artifacts.
- **User value:** Teams can incorporate evidence into existing processes.
- **Priority:** Should have
- **Rationale:** The product already exports CSV, JSON, and Markdown in separate modules.
- **Acceptance criteria:**
  - JSON exports are schema-versioned.
  - CSV fields are documented and stable within a major version.
  - Markdown reports include run identifiers and configuration summary.
  - Time values are ISO 8601 with timezone.
  - Monetary values include currency and sufficient precision.

#### DIR-04: Notification integrations

- **Type:** Data/Integration
- **Description:** The product should route selected alerts and approval requests to configured collaboration channels.
- **User value:** Users do not need to poll the console continuously.
- **Priority:** Could have
- **Rationale:** Approval channels and alert concepts already exist, supporting a logical extension.
- **Acceptance criteria:**
  - Initial integrations support webhook plus at least one team messaging channel.
  - Notification content contains a secure deep link, severity, age, and summary.
  - Sensitive prompt/tool arguments are omitted or redacted by default.
  - Delivery failures are visible and retried according to policy.

### Won't have for now

#### WH-01: General-purpose no-code agent marketplace

- **Type:** Product scope
- **Description:** The next version will not add a public marketplace for arbitrary third-party agents or tools.
- **User value:** Avoids distracting from core comparison, operation, and governance workflows.
- **Priority:** Won't have for now
- **Rationale:** The evidence supports internal tooling and controlled integrations, not marketplace discovery, billing, trust, or moderation.
- **Acceptance criteria:**
  - No marketplace-specific accounts, payments, ratings, or publishing workflow are included in the next-version scope.

#### WH-02: Fully distributed orchestration platform

- **Type:** Product scope
- **Description:** The next version will not attempt general multi-region distributed agent scheduling.
- **User value:** Keeps effort focused on coherent user workflows and operational correctness.
- **Priority:** Won't have for now
- **Rationale:** Local/single-instance foundations and UI gaps should be resolved before distributed execution complexity.
- **Acceptance criteria:**
  - The release may define extension points but does not claim multi-region scheduling or exactly-once distributed execution.

---

## 6. New opportunities

### Opportunity 1: Decision workspace for model and prompt promotion

**Potential capability:** Convert saved comparisons into a structured candidate-versus-baseline decision with quality, latency, cost, reliability, security, and human review evidence.

**Why users may want it:** Teams rarely compare models for curiosity alone. They need to decide what to deploy and justify the change.

**Evidence and reasoning:** The repository already contains a playground, benchmark suite, evaluation gates, cost calculator, traces, and security scans. A promotion workflow combines existing capabilities around a real user goal instead of adding an unrelated feature.

### Opportunity 2: Run replay and “change one thing” experimentation

**Potential capability:** Duplicate a run while highlighting changed configuration and replay only selected attempts or steps.

**Why users may want it:** Prompt and model work is iterative. Users need controlled comparison, not repeated manual reconstruction.

**Evidence and reasoning:** Existing trace, chain step, provider attempt, idempotency, and benchmark concepts create a strong foundation for reproducible replay.

### Opportunity 3: Role-aware operational inbox

**Potential capability:** A prioritized queue for failed runs, pending approvals, budget risks, security blocks, drift alerts, and evaluation failures.

**Why users may want it:** Operators and reviewers act mainly on exceptions. Separate dashboards force polling and context switching.

**Evidence and reasoning:** The product already generates lifecycle states, alerts, findings, approval checkpoints, and anomalies. Consolidating them into an actionable inbox follows observed object relationships.

### Opportunity 4: Organization-specific value scoring

**Potential capability:** Let teams define transparent weights and minimum thresholds for quality, cost, latency, privacy, and reliability, then rank candidates accordingly.

**Why users may want it:** “Fastest” or “cheapest” cannot represent every workload's priorities.

**Evidence and reasoning:** Task profiles, cost recommendations, benchmark metrics, local-provider options, and security policy are already present. A transparent rubric would make selection more trustworthy than a generic badge.

### Opportunity 5: Guided local/private AI mode

**Potential capability:** A clear workflow for selecting Ollama/local models, verifying local connectivity, labeling data locality, and comparing them with hosted alternatives.

**Why users may want it:** Some users prioritize privacy, predictable cost, or offline operation.

**Evidence and reasoning:** Ollama support, local MCP tools, path sandboxing, and security controls already indicate demand for local-first workflows.

### Opportunity 6: Visual workflow inspection before visual authoring

**Potential capability:** Start with a read-only graph/timeline of chain and agent execution, then add replay and breakpoint-like inspection before attempting drag-and-drop creation.

**Why users may want it:** Debugging existing code-defined workflows is a more immediate need than replacing code for developer users.

**Evidence and reasoning:** Chains and agents already produce steps, costs, latency, statuses, delegation, and checkpoints. Visualization is directly supported by existing execution data, while full no-code authoring would require much broader schema and validation work.

---

## 7. Final recommendation

### What should be built first and why

Build a **persistent, progressive comparison workflow inside a unified product shell**.

The first release slice should include:

1. Unified navigation and role-aware home.
2. Provider readiness, model selection, and preflight checks.
3. Persistent comparison runs and attempt records.
4. Progressive result rendering, cancellation, and per-provider retry.
5. Readable result cards with safe Markdown/code rendering.
6. Flexible sorting with explicit metric labels.
7. Run detail linking output, trace, spend, errors, security, and approvals.
8. Functional cost dashboard filtering and drill-down.
9. Consistent accessible status, empty, partial, and recovery states.
10. Version/catalog freshness indicators and documentation alignment.

This sequence is recommended because it improves the application's most accessible and frequent workflow while also creating the data model needed for evaluation, cost analysis, audit, and operational investigation.

### UI and workflow improvements to prioritize immediately

- Replace name-only provider checkboxes with readiness-aware selection.
- Show projected cost and policy blocks before Compare.
- Render each provider independently as it completes.
- Preserve successful results when another provider fails.
- Add Cancel and Retry failed provider.
- Save every run automatically or offer an explicit privacy-aware save policy.
- Provide history, duplicate, and reopen actions.
- Let users sort by cost, latency, quality, and rating.
- Add actionable error messages and direct links to setup or trace details.
- Implement cost dashboard filters and remove disruptive full-page refresh.
- Add skip link, live regions, focus management, and keyboard shortcuts.

### Requirements with the greatest adoption and efficiency impact

1. **FR-01 Persistent comparison run entity**
2. **UR-06 Provider readiness before running**
3. **FR-02 Provider configuration preflight**
4. **UR-02 Progressive comparison feedback**
5. **FR-10 Unified run investigation view**
6. **FR-05 Functional cost analytics filters**
7. **UX-04 Consistent status and recovery patterns**
8. **NFR-01 Accessibility conformance**
9. **BR-02 Traceable model-selection decisions**
10. **DIR-01 Canonical run and correlation model**

### Suggested phased delivery

#### Phase 1: Core daily workflow

Deliver persistent runs, readiness/preflight, progressive execution, retry/cancel, readable results, history, and accessibility. Validate with task-based usability tests for first-run setup, repeated comparison, partial failure, and reopening a saved run.

#### Phase 2: Decision and investigation

Add quality evaluators, human ratings, diffing, unified run detail, trace/spend/security links, functional cost analytics, and exports.

#### Phase 3: Operational scale

Add role-aware inbox, global search, notifications, guided setup, organization-specific scoring, and visual workflow inspection.

### Product success measures

Track:

- Median time from landing to first successful comparison.
- Percentage of runs blocked by preventable setup issues.
- Time to identify and recover from a failed provider attempt.
- Percentage of repeated comparisons launched from a preset or prior run.
- Percentage of decisions with saved evidence and preferred candidate.
- Dashboard filter-to-drill-down completion rate.
- Approval decision time and rejection reason distribution.
- Keyboard-only task completion and accessibility defect rate.
- Cost estimate variance versus actual cost.
- User-reported confidence in provider/model selection.

---

## Analysis limitations and inference notes

- The archive contains code, tests, and documentation, but no user interviews, production analytics, support tickets, or session recordings. Behavioral findings are therefore explicitly inferred from the implemented flows and target roles.
- The report evaluates the application represented in the archive. It does not assume that every documented roadmap item is production-ready.
- Automated tests provide strong contract evidence but do not replace browser-based usability testing, accessibility testing with assistive technology, or field validation with real teams.
- Market opportunities are grounded in existing capabilities and workflow gaps. No unrelated feature categories were added.

## Recommended validation research

Before finalizing implementation detail, run five focused studies:

1. **Developer setup test:** Connect two hosted providers and one local provider, then run a first comparison.
2. **Repeated comparison test:** Reuse a prior prompt/configuration, change one model, and explain the decision.
3. **Failure recovery test:** Diagnose one missing credential, one timeout, and one policy block.
4. **FinOps investigation test:** Find the cause of a daily cost spike and identify affected runs.
5. **Approval test:** Review and decide a sensitive agent checkpoint using only displayed context.

Use task completion, time, error count, backtracking, comprehension, and confidence as primary measures. These studies will validate the highest-impact inferences before the product expands further.
