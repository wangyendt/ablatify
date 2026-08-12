from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_node_launcher_runs_the_python_cli() -> None:
    env = os.environ.copy()
    env["ABLATIFY_PYTHON"] = sys.executable

    result = subprocess.run(
        ["node", str(REPO_ROOT / "bin" / "ablatify.js"), "--version"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert result.stdout.strip() == f"ablatify {package['version']}"


def test_node_launcher_explains_an_invalid_python_override() -> None:
    env = os.environ.copy()
    env["ABLATIFY_PYTHON"] = str(REPO_ROOT / "missing-python")

    result = subprocess.run(
        ["node", str(REPO_ROOT / "bin" / "ablatify.js"), "status"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 3
    assert "Python 3.9 or newer" in result.stderr
    assert "ABLATIFY_PYTHON" in result.stderr
