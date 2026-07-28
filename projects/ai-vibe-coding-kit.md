# ai-vibe-coding-kit

**Status:** 🟢 Active  
**Version:** 0.10.0  
**Domain:** Multi-provider LLM API wrapper with cost tracking, structured output, tool calling, agent orchestration, and enterprise patterns  
**Score:** 8/10  
**Last updated:** 2026-07-28

## Capabilities

- ✅ Multi-Provider LLM Wrapper — 9 providers: OpenAI, Anthropic, DeepSeek, OpenRouter, MiMo, Gemini, Mistral, Cohere, Ollama
- ✅ Structured Output & Tool Calling — JSON mode and function calling
- ✅ Cost Tracking & Analytics — Per-provider/ model breakdown with CSV/JSON export
- ✅ Prompt Chaining Templates — 7 chain patterns (sequential, conditional, parallel, map-reduce, agent-with-tools, HITL, chain-runner)
- ✅ Benchmark Suite — Task definition, orchestration, evaluators, AI-vibe-bench CLI
- ✅ MCP Server — File read/write, web search, Python execution, weather, directory listing
- ✅ LLM Playground — Web-based multi-provider comparison with latency and response highlights
- ✅ CI/CD Pipelines — GitHub Actions: automated test, LLM integration test, Railway deployment
- ✅ **Agent Orchestration** — 4 patterns: sequential pipeline, parallel fan-out/fan-in, hierarchical supervisor, pub/sub event-driven
- ✅ **Error Handling** — AgentCircuitBreaker, AgentRetryPolicy with dead-letter queue, AgentFallback
- ✅ **Foundation Layer** — MessageBus (pub/sub), SharedState (namespace-isolated key-value store)
- ✅ **Enterprise Patterns** — 3 production-grade subsystems for scaling LLM pipelines:
  - Rate Limiting & Quota Management (TokenBucket, SlidingWindowCounter, AdaptiveRateLimiter, QuotaManager)
  - Chaos Engineering (FaultInjector, ExperimentRunner, ChaosScenario, ObservabilityHook)
  - Scheduled Scanning & Monitoring (DriftDetector, PromptRegressionTester, CostAnomalyDetector, SLAChecker, Scheduler)

## Next Steps (v0.11.0+)

- **Streaming in AgentPipeline** — yield per-step tokens as they arrive
- **Agent memory persistence** — conversation history across run() calls for supervisor and workers
- **Visual pipeline debugger** — web UI showing agent call graphs and step-level latency/cost
- **Distributed agent execution** — async agents running on separate processes or machines
- **Auto-scaling worker pools** — dynamic agent registration based on workload
- **Rate limiter persistence** — survival across process restarts (Redis-backed TokenBucket, etc.)
- **Chaos experiment dashboards** — web UI for launching and monitoring fault injection experiments

## Feature Details

| Feature | Location | Tests | Status |
|---------|----------|-------|--------|
| LLM Wrapper | `src/ai_vibe_coding/llm_wrapper.py` | 29 | ✅ |
| Extended Providers | `src/ai_vibe_coding/provider_examples.py` | 82 | ✅ |
| Structured Output | `src/ai_vibe_coding/structured.py` | 11 | ✅ |
| Cost Tracking | `src/ai_vibe_coding/cost_tracker.py` | 22 | ✅ |
| Prompt Chaining | `src/ai_vibe_coding/chain_templates.py` | 50+ | ✅ |
| Agent Team | `src/ai_vibe_coding/agent_team.py` | — | ✅ |
| Agent Templates | `src/ai_vibe_coding/agent_templates.py` | 82 | ✅ |
| Rate Limiting | `src/ai_vibe_coding/rate_limiting.py` | — | ✅ |
| Chaos Engineering | `src/ai_vibe_coding/chaos_engineering.py` | — | ✅ |
| Scheduled Scanning | `src/ai_vibe_coding/scheduled_scanning.py` | — | ✅ |
| Benchmark Suite | `src/ai_vibe_coding/benchmark_runner.py` | 62 | ✅ |
| LLM Playground | `src/ai_vibe_coding/playground.py` | 42 | ✅ |
| MCP Server | `src/ai_vibe_coding/mcp_server.py` | — | ✅ |
| CLI | `src/ai_vibe_coding/cli.py` | — | ✅ |
| Frontend | `static/` | 46 | 🟡 In Progress |

## Metrics

- **Total tests:** 875 (all pass, no API keys needed)
- **Package version:** 0.10.0
- **Python:** 3.11+
- **License:** MIT

## Links

- [GitHub Repository](https://github.com/csaszarzoltan/ai-vibe-coding-kit)
- [Changelog](CHANGELOG.md)
- [Documentation](docs/)
