from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv

if TYPE_CHECKING:
    from wxc_sdk import WebexSimpleApi


class MissingTokenError(RuntimeError):
    pass


def create_api() -> 'WebexSimpleApi':
    from wxc_sdk import WebexSimpleApi

    _load_token_from_dotenv()
    token = os.getenv('WEBEX_ACCESS_TOKEN')
    if not token:
        raise MissingTokenError('WEBEX_ACCESS_TOKEN is required')
    return WebexSimpleApi(tokens=token)


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
            load_dotenv(dotenv_path=env_path, override=False)
