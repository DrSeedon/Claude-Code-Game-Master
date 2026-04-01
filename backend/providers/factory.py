"""Factory for creating AI provider based on available credentials."""

import os
import logging
from pathlib import Path
from typing import Optional
from backend.providers.base import BaseProvider
from backend.providers.anthropic_api import AnthropicAPIProvider
from backend.providers.claude_sdk import ClaudeSDKProvider, SDK_AVAILABLE

logger = logging.getLogger(__name__)


def create_provider(
    provider_type: str = "auto",
    api_key: Optional[str] = None,
    project_root: Optional[Path] = None
) -> BaseProvider:
    """Create appropriate AI provider based on available credentials.

    Selection logic:
    1. If provider_type == "api" → Anthropic API (requires api_key)
    2. If provider_type == "sdk" → Claude SDK (requires subscription)
    3. If provider_type == "auto" (default):
       - If ANTHROPIC_API_KEY exists in env → Anthropic API
       - Otherwise → Claude SDK (subscription)

    Args:
        provider_type: Provider type ("auto", "api", "sdk")
        api_key: Anthropic API key (optional, taken from env if not specified)
        project_root: Project root for SDK provider (needed for cwd)

    Returns:
        BaseProvider instance (AnthropicAPIProvider or ClaudeSDKProvider)

    Raises:
        ValueError: If requested provider is unavailable
    """
    # Get API key from env if not provided
    if api_key is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")

    # Determine project_root if not provided
    if project_root is None:
        # Default - parent directory of backend/
        project_root = Path(__file__).parent.parent.parent.absolute()

    # Automatic provider selection
    if provider_type == "auto":
        if api_key:
            logger.info("🔑 Auto-select provider: Anthropic API (found ANTHROPIC_API_KEY)")
            provider_type = "api"
        else:
            logger.info("🎫 Auto-select provider: Claude SDK (subscription)")
            provider_type = "sdk"

    # Create API provider
    if provider_type == "api":
        if not api_key:
            raise ValueError(
                "Anthropic API provider requires ANTHROPIC_API_KEY. "
                "Set in .env file or use AI_PROVIDER=sdk"
            )
        logger.info("✅ Using provider: Anthropic API")
        return AnthropicAPIProvider(api_key=api_key)

    # Create SDK provider
    elif provider_type == "sdk":
        if not SDK_AVAILABLE:
            raise ValueError(
                "Claude SDK not installed. Install with: pip install claude-agent-sdk\n"
                "Or use AI_PROVIDER=api with ANTHROPIC_API_KEY"
            )
        logger.info("✅ Using provider: Claude SDK (subscription)")
        return ClaudeSDKProvider(project_root=project_root)

    else:
        raise ValueError(
            f"Unknown provider type: {provider_type}. "
            f"Available: 'auto', 'api', 'sdk'"
        )
