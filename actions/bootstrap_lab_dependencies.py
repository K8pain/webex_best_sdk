#!/usr/bin/env python3
"""Prepara dependencias reales en el tenant de laboratorio y genera comandos por script."""

from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import logging
import os
from pathlib import Path
from typing import Any

import requests

from _shared import _required_optional_vars
from generate_dummy_users import build_users

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


class WebexClient:
    def __init__(self, base_url: str, token: str, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        )

    def request(self, method: str, path: str, *, params: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> requests.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            return self.session.request(method=method, url=url, params=params, json=payload, timeout=self.timeout)
        except requests.RequestException as err:
            raise RuntimeError(f"request failed {method} {url}: {err}") from err


def _load_action_specs() -> dict[str, Any]:
    specs: dict[str, Any] = {}
    for path in sorted(glob.glob("actions/action_*.py")):
        name = Path(path).stem
        spec_def = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec_def)
        assert spec_def and spec_def.loader
        spec_def.loader.exec_module(module)
        specs[name] = module.SPEC
    return specs


def _lookup_person_by_email(client: WebexClient, email: str) -> dict[str, Any] | None:
    response = client.request("GET", "people", params={"email": email})
    if response.status_code != 200:
        return None
    items = response.json().get("items", [])
    return items[0] if items else None


def _pick_calling_license(client: WebexClient, logger: logging.Logger) -> str | None:
    response = client.request("GET", "licenses")
    if response.status_code != 200:
        logger.warning("No se pudieron listar licencias: %s", response.status_code)
        return None
    items = response.json().get("items", [])
    for item in items:
        name = str(item.get("name", "")).lower()
        if "calling" in name:
            return item.get("id")
    return items[0].get("id") if items else None


def _ensure_people(
    client: WebexClient,
    *,
    location_id: str,
    users_count: int,
    domain: str,
    ext_start: int,
    phone_prefix: str,
    calling_license_id: str | None,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    users = build_users(users_count, domain=domain, ext_start=ext_start, phone_prefix=phone_prefix)
    ensured: list[dict[str, Any]] = []

    for user in users:
        try:
            existing = _lookup_person_by_email(client, user.email)
        except RuntimeError as err:
            logger.error("Lookup usuario falló (%s): %s", user.email, err)
            continue

        if existing:
            logger.info("Usuario ya existe: %s", user.email)
            ensured.append({"id": existing.get("id", ""), "email": user.email})
            continue

        payload: dict[str, Any] = {
            "emails": [user.email],
            "displayName": user.display_name,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "locationId": location_id,
        }
        if calling_license_id:
            payload["licenses"] = [calling_license_id]

        try:
            create = client.request("POST", "people", payload=payload)
        except RuntimeError as err:
            logger.error("Create usuario falló (%s): %s", user.email, err)
            continue

        if create.status_code not in (200, 201):
            logger.error("No se pudo crear usuario %s: %s %s", user.email, create.status_code, create.text[:300])
            continue

        body = create.json()
        ensured.append({"id": body.get("id", ""), "email": user.email})
        logger.info("Usuario creado: %s", user.email)

    return ensured


def _ensure_group(client: WebexClient, group_name: str, logger: logging.Logger) -> str | None:
    try:
        listed = client.request("GET", "groups", params={"filter": group_name})
    except RuntimeError as err:
        logger.warning("No se pudo consultar grupos: %s", err)
        return None

    if listed.status_code == 200:
        payload = listed.json()
        for item in payload.get("Resources", []) + payload.get("items", []):
            if item.get("displayName") == group_name:
                return item.get("id")

    try:
        create = client.request("POST", "groups", payload={"displayName": group_name})
    except RuntimeError as err:
        logger.warning("No se pudo crear grupo '%s': %s", group_name, err)
        return None

    if create.status_code not in (200, 201):
        logger.warning("No se pudo crear grupo '%s': %s", group_name, create.status_code)
        return None
    return create.json().get("id")


def _resolve_workspace_id(client: WebexClient, workspace_name: str, logger: logging.Logger) -> str | None:
    try:
        response = client.request("GET", "workspaces", params={"displayName": workspace_name, "max": 20})
    except RuntimeError as err:
        logger.warning("No se pudo consultar workspace '%s': %s", workspace_name, err)
        return None

    if response.status_code != 200:
        return None
    for item in response.json().get("items", []):
        if item.get("displayName") == workspace_name:
            return item.get("id")
    return None


def _build_var_pool(args: argparse.Namespace, people: list[dict[str, Any]], role_id: str | None, group_id: str | None, workspace_id: str | None) -> dict[str, str]:
    person_id = people[0].get("id", "") if len(people) >= 1 else args.person_id
    member_id = people[1].get("id", "") if len(people) >= 2 else (person_id or args.member_id)
    assistant_id = people[2].get("id", "") if len(people) >= 3 else (person_id or args.assistant_person_id)

    return {
        "aa_name": args.aa_name,
        "assistant_person_id": assistant_id or "",
        "device_model": args.device_model,
        "dial_pattern": args.dial_pattern,
        "dial_plan_name": args.dial_plan_name,
        "email": people[0].get("email", args.email) if people else args.email,
        "extension": str(args.extension),
        "forward_destination": args.forward_destination,
        "group_id": group_id or args.group_id,
        "group_name": args.group_name,
        "hunt_name": args.hunt_name,
        "location_id": args.location_id,
        "member_id": member_id or "",
        "person_id": person_id or "",
        "pickup_name": args.pickup_name,
        "primary_number": args.primary_number,
        "principal_id": person_id or "",
        "queue_id": args.queue_id,
        "queue_name": args.queue_name,
        "role_id": role_id or args.role_id,
        "route_group_id": args.route_group_id,
        "route_group_name": args.route_group_name,
        "schedule_name": args.schedule_name,
        "scope": args.scope,
        "secondary_number": args.secondary_number,
        "serial": args.serial,
        "target_person_id": member_id or "",
        "trunk_id": args.trunk_id,
        "trunk_name": args.trunk_name,
        "workspace_id": workspace_id or args.workspace_id,
        "workspace_name": args.workspace_name,
    }


def _generate_outputs(var_pool: dict[str, str], output_json: Path, output_md: Path) -> list[str]:
    specs = _load_action_specs()
    per_script: dict[str, dict[str, str]] = {}
    missing_keys: list[str] = []

    lines: list[str] = [
        "# Comandos de prueba por script (lab preparado)",
        "",
        "Estos comandos usan IDs reales/dummy preparados por `bootstrap_lab_dependencies.py`.",
        "",
    ]

    for name, spec in specs.items():
        required, optional = _required_optional_vars(spec)
        payload: dict[str, str] = {}
        for key in required:
            value = var_pool.get(key, "")
            if not value:
                missing_keys.append(f"{name}:{key}")
                value = f"MISSING_{key}"
            payload[key] = value
        per_script[name] = payload

        lines.append(f"## {name}.py")
        lines.append(f"- Required `--vars`: `{', '.join(required) if required else '(none)'}`")
        lines.append(f"- Optional `--vars`: `{', '.join(optional) if optional else '(none)'}`")
        lines.append(f"- Dependencias/espera de servidor: {' / '.join(spec.pre_post_notes)}")
        lines.append("```bash")
        lines.append(f"python actions/{name}.py --mode apply --vars '{json.dumps(payload, ensure_ascii=False)}'")
        lines.append("```")
        lines.append("")

    output_json.write_text(json.dumps({"var_pool": var_pool, "per_script": per_script, "missing": missing_keys}, indent=2, ensure_ascii=False), encoding="utf-8")
    output_md.write_text("\n".join(lines), encoding="utf-8")
    return missing_keys


def main() -> int:
    parser = argparse.ArgumentParser(description="Sube usuarios dummy y prepara dependencias mínimas para pruebas en lab")
    parser.add_argument("--base-url", default=os.getenv("WEBEX_BASE_URL", "https://webexapis.com/v1"))
    parser.add_argument("--token", default=os.getenv("WEBEX_ACCESS_TOKEN"))
    parser.add_argument("--location-id", required=True)
    parser.add_argument("--users-count", type=int, default=3)
    parser.add_argument("--domain", default="lab.example.com")
    parser.add_argument("--ext-start", type=int, default=5101)
    parser.add_argument("--phone-prefix", default="+3491")
    parser.add_argument("--calling-license-id", default=None)
    parser.add_argument("--output-json", default="actions/lab_bootstrap_output.json")
    parser.add_argument("--output-commands", default="actions/script_test_commands_lab.md")
    parser.add_argument("--strict", action="store_true", help="falla si falta alguna dependencia")
    parser.add_argument("--timeout", type=int, default=20)

    parser.add_argument("--workspace-name", default="WS-LAB-REUNIONES")
    parser.add_argument("--workspace-id", default="")
    parser.add_argument("--group-name", default="LAB-GROUP-VOICE")
    parser.add_argument("--group-id", default="")
    parser.add_argument("--queue-id", default="")
    parser.add_argument("--queue-name", default="CQ-LAB-VENTAS")
    parser.add_argument("--route-group-id", default="")
    parser.add_argument("--route-group-name", default="RG-LAB-SBC")
    parser.add_argument("--trunk-id", default="")
    parser.add_argument("--trunk-name", default="TRUNK-LAB-MAIN")
    parser.add_argument("--role-id", default="")

    parser.add_argument("--aa-name", default="AA-LAB-MADRID")
    parser.add_argument("--dial-pattern", default="+3491XXXXXXX")
    parser.add_argument("--dial-plan-name", default="DP-LAB-INTERPLATFORM")
    parser.add_argument("--schedule-name", default="Horario-LAB-LV")
    parser.add_argument("--pickup-name", default="PG-LAB-RECEPCION")
    parser.add_argument("--hunt-name", default="HG-LAB-SOPORTE")
    parser.add_argument("--scope", default="organization")
    parser.add_argument("--device-model", default="Cisco 8851")
    parser.add_argument("--serial", default="FTX1234LAB1")
    parser.add_argument("--primary-number", default="+34915550101")
    parser.add_argument("--secondary-number", default="+34915550222")
    parser.add_argument("--forward-destination", default="+34915550123")
    parser.add_argument("--extension", type=int, default=5101)
    parser.add_argument("--person-id", default="")
    parser.add_argument("--member-id", default="")
    parser.add_argument("--assistant-person-id", default="")
    parser.add_argument("--email", default="dummy.user.lab@lab.example.com")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    logger = logging.getLogger("bootstrap_lab")

    if not args.token:
        logger.error("Falta token: usa --token o WEBEX_ACCESS_TOKEN")
        return 2

    client = WebexClient(base_url=args.base_url, token=args.token, timeout=args.timeout)

    try:
        calling_license_id = args.calling_license_id or _pick_calling_license(client, logger)
    except RuntimeError as err:
        logger.warning("No se pudo resolver licencia: %s", err)
        calling_license_id = args.calling_license_id

    people = _ensure_people(
        client,
        location_id=args.location_id,
        users_count=args.users_count,
        domain=args.domain,
        ext_start=args.ext_start,
        phone_prefix=args.phone_prefix,
        calling_license_id=calling_license_id,
        logger=logger,
    )

    group_id = _ensure_group(client, args.group_name, logger) or args.group_id
    workspace_id = _resolve_workspace_id(client, args.workspace_name, logger) or args.workspace_id

    role_id = args.role_id
    if not role_id:
        try:
            role_resp = client.request("GET", "roles")
            if role_resp.status_code == 200:
                items = role_resp.json().get("items", [])
                role_id = items[0].get("id") if items else ""
        except RuntimeError as err:
            logger.warning("No se pudo resolver role_id automáticamente: %s", err)

    pool = _build_var_pool(args, people, role_id, group_id, workspace_id)
    output_json = Path(args.output_json)
    output_md = Path(args.output_commands)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    missing = _generate_outputs(pool, output_json, output_md)

    logger.info("Usuarios preparados/encontrados: %s", len(people))
    logger.info("Output vars: %s", output_json)
    logger.info("Output comandos: %s", output_md)
    if missing:
        logger.warning("Dependencias faltantes (%s): %s", len(missing), ", ".join(missing))
        if args.strict:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
