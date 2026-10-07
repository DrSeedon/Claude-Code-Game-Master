"""Prevent credentials from entering files tracked by Git."""

import re
import subprocess
from pathlib import Path

import pytest
from dotenv import dotenv_values


REPO_ROOT = Path(__file__).resolve().parents[1]
SECRET_NAME = re.compile(r"(?:KEY|TOKEN|PASSWORD|PASSWD|SECRET)", re.IGNORECASE)
PLACEHOLDER = re.compile(
    r"(?:^|[_-])(?:example|placeholder|your|change[-_]?me|replace[-_]?me|"
    r"dummy|sample|test|xxx)(?:$|[_-])",
    re.IGNORECASE,
)
TOKEN_PATTERNS = (
    ("Anthropic token", re.compile(rb"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("OpenAI token", re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token", re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b")),
    ("Telegram bot token", re.compile(rb"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b")),
    ("Slack token", re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("Google API key", re.compile(rb"\bAIza[A-Za-z0-9_-]{30,}\b")),
    ("AWS access key", re.compile(rb"\bAKIA[A-Z0-9]{16}\b")),
)
ASSIGNMENT = re.compile(
    rb"(?i)\b(password|passwd|api[_-]?key|access[_-]?token|auth[_-]?token|"
    rb"secret[_-]?key)\b\s*[:=]\s*[\"'`]?([^\s\"'`,;}`]{8,})"
)


def tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [root / name.decode("utf-8", errors="surrogateescape") for name in result.stdout.split(b"\0") if name]


def secret_values(root: Path) -> list[tuple[str, bytes]]:
    env_path = root / ".env"
    if not env_path.is_file():
        return []
    values = dotenv_values(env_path)
    secrets = []
    for name, value in values.items():
        if not name or value is None:
            continue
        if name != "DND_AUTH_PASSWORD" and not SECRET_NAME.search(name):
            continue
        if not value or PLACEHOLDER.search(value):
            continue
        secrets.append((name, value.encode("utf-8")))
    return secrets


def value_findings(root: Path) -> list[tuple[str, int, str]]:
    known_secrets = secret_values(root)
    results = []
    for path in tracked_files(root):
        content = path.read_bytes()
        relative = path.relative_to(root).as_posix()
        for name, secret in known_secrets:
            start = 0
            while (offset := content.find(secret, start)) >= 0:
                line = content.count(b"\n", 0, offset) + 1
                results.append((relative, line, name))
                start = offset + len(secret)
    return sorted(set(results))


def pattern_findings(root: Path) -> list[tuple[str, int, str]]:
    results = []
    for path in tracked_files(root):
        content = path.read_bytes()
        relative = path.relative_to(root).as_posix()
        for label, pattern in TOKEN_PATTERNS:
            for match in pattern.finditer(content):
                line = content.count(b"\n", 0, match.start()) + 1
                results.append((relative, line, label))
        for match in ASSIGNMENT.finditer(content):
            name = match.group(1).decode("ascii").upper().replace("-", "_")
            value = match.group(2).decode("utf-8", errors="ignore")
            if (
                PLACEHOLDER.search(value)
                or value.startswith("_")
                or value.lower() in {"test-password", "secret", "password"}
            ):
                continue
            if len(value) < 8:
                continue
            line = content.count(b"\n", 0, match.start(2)) + 1
            results.append((relative, line, name))
    return sorted(set(results))


def raise_for_findings(issues: list[tuple[str, int, str]]) -> None:
    if issues:
        details = "\n".join(f"{path}:{line}: {name}" for path, line, name in issues)
        raise AssertionError(f"Potential secrets found in tracked files:\n{details}")


def test_env_secret_values_are_not_tracked():
    if not (REPO_ROOT / ".env").is_file():
        pytest.skip(".env not present; local secret values cannot be checked")
    raise_for_findings(value_findings(REPO_ROOT))


def test_common_secret_patterns_are_not_tracked():
    raise_for_findings(pattern_findings(REPO_ROOT))


def test_duckdns_token_is_ignored_and_untracked():
    ignored = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", "--quiet", ".duckdns_token"]
    ).returncode
    tracked = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--error-unmatch", ".duckdns_token"],
        capture_output=True,
    ).returncode
    assert ignored == 0
    assert tracked != 0
