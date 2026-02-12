from __future__ import annotations

import os
from typing import Callable

from wxc_sdk import WebexSimpleApi


def build_sdk_client(
    *,
    token: str | None = None,
    token_env_var: str = "WEBEX_ACCESS_TOKEN",
    api_factory: Callable[..., WebexSimpleApi] = WebexSimpleApi,
) -> WebexSimpleApi:
    resolved_token = token or os.getenv(token_env_var)
    if not resolved_token:
        raise ValueError(f"Missing access token: provide token or set {token_env_var}")
    return api_factory(tokens=resolved_token)
