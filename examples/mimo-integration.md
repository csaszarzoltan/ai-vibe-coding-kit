# Xiaomi MiMo Integration Guide

How to use Xiaomi MiMo API for cost-effective AI coding assistance.

## Why MiMo?

- **40-60% fewer tokens** than Claude Opus 4.7
- **$0.40/$2.00 per 1M tokens** (vs $15/$75 for Claude)
- **1M token context window**
- **Open-source** - can self-host
- **SWE-bench score: 78%** (competitive with Claude 4)

## Setup

```bash
pip install requests
```

```python
import requests

API_KEY = "your-mimo-api-key"
BASE_URL = "https://api.xiaomimimo.com/v1"

response = requests.post(
    f"{BASE_URL}/chat/completions",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
        "model": "mimo-v2.5",
        "messages": [
            {"role": "user", "content": "Write a Python function..."}
        ]
    }
)
```

## When to Use MiMo

✅ Good for:
- Code generation and refactoring
- Documentation and comments
- Test case generation
- Simple debugging

⚠️ Less ideal for:
- Complex reasoning tasks
- Creative architectural decisions
- Production-critical logic without human review

## Cost Comparison

| Task | GPT-4 | Claude 4 | MiMo V2.5 |
|------|-------|----------|-----------|
| 1K prompt, 2K completion | $0.06 | $0.09 | $0.004 |
| 10K prompt, 5K completion | $0.40 | $0.60 | $0.027 |
| 100K prompt, 20K completion | $4.00 | $6.00 | $0.28 |
