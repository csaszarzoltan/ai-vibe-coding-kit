# Test Results

## Baseline before modification

Command: `pytest -q`

- 919 passed
- 78 failed
- 11 warnings

The failures were already present in the supplied archive. They cover staged provider adapter behavior, MCP optional dependency/runtime behavior, cost API placeholder expectations, and one async wrapper contract.

## TDD RED phase

Command: `pytest -q tests/test_next_version_ux.py`

- 3 failed as expected before implementation
- Missing: provider readiness endpoint, accessible/history markup, and persistence/telemetry helpers

## Targeted regression after implementation

Command:

```bash
pytest -q tests/test_next_version_ux.py tests/test_frontend_playground.py tests/test_playground.py tests/test_app.py
```

- 92 passed
- 0 failed
- 1 dependency deprecation warning

## Full regression after implementation in a clean project environment

A clean virtual environment was created and all declared development dependencies plus the documented MCP dependency were installed:

```bash
uv venv /mnt/data/testenv
uv pip install --python /mnt/data/testenv/bin/python -e ".[dev]" "mcp>=1.27,<2"
pytest -q
```

Result:

- **1000 passed**
- **0 failed**
- **1 third-party deprecation warning**

The earlier 78 failures were environment-related: the initial runner did not have the project's optional provider SDKs or MCP package installed. The clean-environment result is recorded in `reports/full_regression_clean_environment.txt`.

## Lint

Modified Python files pass Ruff:

```bash
ruff check src/ai_vibe_coding/app.py src/ai_vibe_coding/playground.py tests/test_next_version_ux.py
```

The repository-wide Ruff run reports pre-existing style debt in untouched files. Its output is included at `reports/ruff_repository_output.txt`.

## Continuation validation

A second TDD cycle first produced two expected failures for missing visible readiness integration and missing wheel package-data declarations. After implementation:

- Next-version UX tests: **5 passed**
- Complete regression suite: **1002 passed, 0 failed**
- Modified Python files: **Ruff passed**
- Wheel build: **passed**
- Packaged HTML, JavaScript, and CSS assets: **verified present**

## Actionable error and retry validation

A third RED cycle captured three expected failures for missing error metadata, scoped retry, and accessible recovery styling. After implementation:

- Next-version UX tests: **8 passed**
- Targeted playground regression: **97 passed, 0 failed**
- Complete regression suite: **1005 passed, 0 failed**
- Modified Python files: **Ruff passed**
- Wheel build and static-asset validation: **passed**
