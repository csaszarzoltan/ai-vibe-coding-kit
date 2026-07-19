"""Conftest for ai-vibe-coding-kit tests.

Adds src/ to sys.path so `import ai_vibe_coding` works without installation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
