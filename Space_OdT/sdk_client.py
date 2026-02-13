from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv

if TYPE_CHECKING:
    from wxc_sdk import WebexSimpleApi


class MissingTokenError(RuntimeError):
    pass


def resolve_access_token(explicit_token: str | None = None) -> str:
    """Resolve access token from explicit CLI arg or .env/environment fallback."""
    selected_token = explicit_token
    if selected_token is None:
        _load_token_from_dotenv()
        selected_token = os.getenv('WEBEX_ACCESS_TOKEN')
    if not selected_token:
        raise MissingTokenError('WEBEX_ACCESS_TOKEN is required (or pass --token)')
    return selected_token


def create_api(token: str | None = None) -> 'WebexSimpleApi':
    from wxc_sdk import WebexSimpleApi

    selected_token = resolve_access_token(token)
    return WebexSimpleApi(tokens=selected_token)


def _load_token_from_dotenv() -> None:
    """Load WEBEX_ACCESS_TOKEN from .env files in CWD, ancestors, or project root."""
    cwd = Path.cwd()
    package_root = Path(__file__).resolve().parents[1]

    env_candidates = [cwd / '.env', *[parent / '.env' for parent in cwd.parents], package_root / '.env']

    seen = set()
    for env_path in env_candidates:
        resolved = str(env_path.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        if env_path.is_file():
            # Prefer deterministic .env-based auth for Space_OdT runs, even when
            # a stale WEBEX_ACCESS_TOKEN is already present in the shell env.
            load_dotenv(dotenv_path=env_path, override=True)
