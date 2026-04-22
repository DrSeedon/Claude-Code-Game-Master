"""Factory for AI provider selection based on available credentials."""

import os
import logging
from pathlib import Path
from typing import Optional

from backend.providers.base import BaseProvider
from backend.providers.anthropic_api import AnthropicAPIProvider
from backend.providers.claude_sdk import ClaudeSDKProvider

logger = logging.getLogger(__name__)


def create_provider(
    provider_type: str = "auto",
    api_key: Optional[str] = None,
    project_root: Optional[Path] = None,
    ephemeral: bool = False,
    model_name: str = "claude-sonnet-4-6",
) -> BaseProvider:
    """Create appropriate AI provider.

    Selection:
      provider_type="api"  → AnthropicAPIProvider (needs api_key)
      provider_type="sdk"  → ClaudeSDKProvider (needs CLI auth)
      provider_type="auto" → API if ANTHROPIC_API_KEY set, else SDK

    Args:
        provider_type: "auto" | "api" | "sdk"
        api_key: explicit API key; falls back to env ANTHROPIC_API_KEY
        project_root: project root (SDK needs it for cwd)
        ephemeral: SDK-only; skip session persistence (wizard-style flows)
        model_name: default Claude model

    Returns:
        Provider instance (unbound to any session — caller must call load_session)
    """
    if api_key is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent.absolute()

    if provider_type == "auto":
        provider_type = "api" if api_key else "sdk"
        logger.info("Auto-selected provider: %s", provider_type)

    if provider_type == "api":
        if not api_key:
            raise ValueError(
                "Anthropic API provider requires ANTHROPIC_API_KEY. "
                "Set in .env or use AI_PROVIDER=sdk"
            )
        return AnthropicAPIProvider(api_key=api_key)

    if provider_type == "sdk":
        return ClaudeSDKProvider(
            project_root=project_root,
            model_name=model_name,
            ephemeral=ephemeral,
        )

    raise ValueError(
        f"Unknown provider type: {provider_type}. Available: auto, api, sdk"
    )
