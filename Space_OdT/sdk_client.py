from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wxc_sdk import WebexSimpleApi


class MissingTokenError(RuntimeError):
    pass


def resolve_access_token(explicit_token: str | None = None) -> str:
    """Resolve access token from explicit CLI arg or process environment."""
    selected_token = explicit_token if explicit_token is not None else os.getenv('WEBEX_ACCESS_TOKEN')
    if selected_token is None or not selected_token.strip():
        raise MissingTokenError('WEBEX_ACCESS_TOKEN is required (or pass --token)')
    return selected_token.strip()


def create_api(token: str | None = None) -> 'WebexSimpleApi':
    from wxc_sdk import WebexSimpleApi

    selected_token = resolve_access_token(token)
    return WebexSimpleApi(tokens=selected_token)
