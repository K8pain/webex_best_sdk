from __future__ import annotations

import os

from wxc_sdk import WebexSimpleApi


class MissingTokenError(RuntimeError):
    pass


def create_api() -> WebexSimpleApi:
    token = os.getenv('WEBEX_ACCESS_TOKEN')
    if not token:
        raise MissingTokenError('WEBEX_ACCESS_TOKEN is required')
    return WebexSimpleApi(tokens=token)
