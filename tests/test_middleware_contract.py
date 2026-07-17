import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
COMMON_ADVANCED = (
    PROJECT_ROOT / ".claude" / "additional" / "infrastructure" / "common-advanced.sh"
)


def run_dispatch(tmp_path: Path, middleware_exit: int) -> subprocess.CompletedProcess:
    middleware = (
        tmp_path
        / ".claude"
        / "additional"
        / "modules"
        / "test-module"
        / "middleware"
        / "dm-test.sh"
    )
    middleware.parent.mkdir(parents=True)
    middleware.write_text(
        f"#!/usr/bin/env bash\nexit {middleware_exit}\n",
        encoding="utf-8",
    )
    script = f"""
PROJECT_ROOT={str(tmp_path)!r}
source {str(COMMON_ADVANCED)!r}
_module_enabled() {{ return 0; }}
dispatch_middleware dm-test.sh action
"""
    return subprocess.run(
        ["bash", "-c", script],
        text=True,
        capture_output=True,
        check=False,
    )


def test_middleware_not_applicable_returns_64(tmp_path):
    assert run_dispatch(tmp_path, 64).returncode == 64


def test_middleware_operational_failure_is_not_hidden(tmp_path):
    assert run_dispatch(tmp_path, 7).returncode == 7


def test_middleware_handled_success_returns_zero(tmp_path):
    assert run_dispatch(tmp_path, 0).returncode == 0
