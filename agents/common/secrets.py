"""Secrets Management for Agora v4.0.

Provides a unified interface to load API keys from either Cloud Run volume mounts
(/secrets/) or fallback to local environment variables during development.
"""

import os
import pathlib

_SECRETS_DIR = pathlib.Path("/secrets")

def get_secret(key: str, default: str = "") -> str:
    """Retrieve a secret, prioritizing Cloud Run volume mounts over os.environ.

    Args:
        key: The secret name (e.g., "GEMINI_API_KEY").
        default: Fallback value if not found.

    Returns:
        The secret value as a string.
    """
    secret_path = _SECRETS_DIR / key
    if secret_path.exists():
        try:
            return secret_path.read_text(encoding="utf-8").strip()
        except Exception:
            pass  # Fall back to env var on failure
    
    return os.environ.get(key, default)
