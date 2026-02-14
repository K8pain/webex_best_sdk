from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from wxc_sdk import WebexSimpleApi


def load_runtime_env() -> None:
    cwd = Path.cwd()
    package_root = Path(__file__).resolve().parents[3]
    env_candidates = [cwd / '.env', *[parent / '.env' for parent in cwd.parents], package_root / '.env']
    seen: set[str] = set()
    for env_path in env_candidates:
        resolved = str(env_path.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        if env_path.is_file():
            load_dotenv(dotenv_path=env_path, override=True)


def get_token(explicit_token: str | None = None) -> str:
    token = explicit_token or os.getenv('WEBEX_ACCESS_TOKEN')
    if not token:
        raise ValueError('WEBEX_ACCESS_TOKEN no definido (ni --token).')
    return token


def create_api(token: str) -> WebexSimpleApi:
    return WebexSimpleApi(tokens=token)


def action_logger(script_name: str):
    log_file = Path(__file__).resolve().parent / 'logs' / f'{script_name}.log'
    log_file.parent.mkdir(parents=True, exist_ok=True)

    def _log(event: str, payload: dict[str, Any]) -> None:
        line = {
            'ts': dt.datetime.now(dt.timezone.utc).isoformat(),
            'action_id': script_name,
            'event': event,
            'payload': payload,
        }
        with log_file.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + '\n')

    return _log


def model_to_dict(value: Any) -> Any:
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json', by_alias=True, exclude_none=True)
    if isinstance(value, list):
        return [model_to_dict(item) for item in value]
    return value
