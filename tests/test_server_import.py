import os
import subprocess
import sys
from pathlib import Path


def test_server_imports_in_a_fresh_interpreter():
    project_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "-c", "import backend.server"],
        cwd=project_root,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
