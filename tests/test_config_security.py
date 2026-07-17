from pathlib import Path

import pytest

from backend.config import Config, validate_server_security


def config_for(host: str) -> Config:
    root = Path("/tmp/project")
    return Config(
        project_root=root,
        world_state_base=root / "world-state",
        campaigns_dir=root / "world-state" / "campaigns",
        backend_host=host,
    )


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_loopback_server_can_run_without_password(host):
    validate_server_security(config_for(host), password="")


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.20", "dm.local"])
def test_external_server_requires_password(host):
    with pytest.raises(RuntimeError, match="DND_AUTH_PASSWORD"):
        validate_server_security(config_for(host), password="")


def test_external_server_accepts_password():
    validate_server_security(config_for("0.0.0.0"), password="secret")
