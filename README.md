# 🤖 AI Vibe Coding Kit

Production-ready AI development workflows, vibe coding templates, and LLM automation examples. Built for Python developers who want to ship faster with Cursor, Claude Code, MiMo, and modern AI tools.

## 📦 What's Inside

### Vibe Coding Workflows
- **`examples/cursor-workflow.md`** - Step-by-step vibe coding workflow with Cursor
- **`examples/claude-code-workflow.md`** - Autonomous coding with Claude Code
- **`examples/mimo-integration.md`** - Using Xiaomi MiMo API for cost-effective AI coding
- **`examples/openai-workflow.md`** - GPT-4/5 integration patterns

### LLM Automation Templates
- **`examples/llm-api-wrapper.py`** - Unified interface for multiple LLM providers
- **`examples/rag-pipeline.py`** - Retrieval-Augmented Generation with LangChain
- **`examples/ai-agent-workflow.py`** - Autonomous AI agent with tool use
- **`examples/prompt-engineering-guide.md`** - Best practices for coding prompts

### CI/CD + AI Integration
- **`.github/workflows/ai-ci.yml`** - Automated code review, testing, and AI suggestions
- **`examples/n8n-workflows/`** - No-code automation with n8n
- **`examples/make-scenarios/`** - Make.com automation templates

### Cost Optimization
- **`docs/model-comparison.md`** - GPT-4 vs Claude vs MiMo vs DeepSeek pricing
- **`docs/best-practices.md`** - How to minimize API costs while maximizing quality
- **`docs/caching-strategies.md`** - Reduce token usage with smart caching

## 🚀 Quick Start

```bash
git clone https://github.com/csaszarzoltan/ai-vibe-coding-kit.git
cd ai-vibe-coding-kit
pip install -r requirements.txt
```

### Example: Multi-LLM Wrapper

```python
from examples.llm_api_wrapper import LLMClient

# Use any provider with the same interface
client = LLMClient(provider="openai")
response = client.chat("Explain this code: ...")

# Switch to cheaper/faster provider
client = LLMClient(provider="mimo")
response = client.chat("Write a Python function: ...")
```

## 🛠️ Tech Stack

- **AI Models:** OpenAI GPT, Anthropic Claude, Xiaomi MiMo, DeepSeek
- **Tools:** Cursor, Claude Code, OpenCode, Continue.dev
- **Frameworks:** LangChain, LlamaIndex, CrewAI
- **Automation:** n8n, Make.com, Zapier
- **Languages:** Python, JavaScript/TypeScript

## 💡 Use Cases

- **Rapid prototyping** - Build MVPs in days, not weeks
- **Code automation** - Generate tests, docs, migrations automatically
- **Legacy modernization** - AI-assisted refactoring
- **AI integration** - Add LLM features to existing apps
- **Workflow automation** - Connect tools with AI-powered logic

## 📚 Documentation

- [Cursor Workflow Guide](examples/cursor-workflow.md)
- [Claude Code Tips](examples/claude-code-workflow.md)
- [MiMo Integration](examples/mimo-integration.md)
- [Cost Optimization](docs/cost-optimization.md)

## 🎯 Perfect For

- Startup founders who need to move fast
- Indie hackers building SaaS products
- Teams wanting to 10x development velocity
- Anyone curious about vibe coding

## 📞 Contact

**Zoltan Csaszar**
- Upwork: [Profile](https://www.upwork.com/freelancers/~010b8149572fd46b3d)
- GitHub: [@csaszarzoltan](https://github.com/csaszarzoltan)

---

⭐ **Star this repo if you find it useful!**
