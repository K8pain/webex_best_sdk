#!/usr/bin/env python3
from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Dict, Any

import pandas as pd
import yaml
from wxc_sdk import WebexSimpleApi


def _norm(s: str) -> str:
    return str(s).strip().lower()


def main(argv: list[str]) -> int:
    # Usage: script.py map.yaml file_in.xlsx file_out.xlsx
    if len(argv) != 3:
        print("Usage: script.py map.yaml file_in.xlsx file_out.xlsx", file=sys.stderr)
        return 2

    map_yaml_path: Path = Path(argv[0]).expanduser().resolve()
    file_in: Path = Path(argv[1]).expanduser().resolve()
    file_out: Path = Path(argv[2]).expanduser().resolve()

    if not map_yaml_path.exists() or not file_in.exists():
        print("Missing map.yaml or input file.", file=sys.stderr)
        return 2

    token: str = os.getenv("WEBEX_ACCESS_TOKEN", "").strip()
    if not token:
        print("Set WEBEX_ACCESS_TOKEN env var.", file=sys.stderr)
        return 2

    api: WebexSimpleApi = WebexSimpleApi(tokens=token)

    with map_yaml_path.open("r", encoding="utf-8") as f:
        m: Dict[str, Any] = yaml.safe_load(f)

    idx: Dict[str, Dict[str, Any]] = m.get("index", {})

    # Preload lookup tables (name -> id)
    loc_index: Dict[str, str] = {
        _norm(getattr(l, "name", "")): getattr(l, "location_id", "") or getattr(l, "id", "")
        for l in api.locations.list()
    }
    ws_index: Dict[str, str] = {
        _norm(getattr(w, "display_name", "") or getattr(w, "title", "") or getattr(w, "name", "")):
        getattr(w, "workspace_id", "") or getattr(w, "id", "")
        for w in api.workspaces.list()
    }

    xls = pd.ExcelFile(file_in)
    with pd.ExcelWriter(file_out, engine="openpyxl") as writer:
        for sheet in xls.sheet_names:
            df: pd.DataFrame = pd.read_excel(file_in, sheet_name=sheet)

            if sheet not in idx:
                df.to_excel(writer, index=False, sheet_name=sheet)
                continue

            sheet_map: Dict[str, Any] = idx[sheet]

            # Build email if split (Usuari + Domini)
            if "Usuari" in df.columns and "Domini" in df.columns:
                df["email"] = (
                    df["Usuari"].astype(str).str.strip() + "@" + df["Domini"].astype(str).str.strip()
                ).str.lower()

            for col, entry in sheet_map.items():
                tgt: str = str(entry.get("target_parametro", "")).strip()
                need_lookup: bool = str(entry.get("lookup_required", "")).upper() == "YES"
                if not tgt or col not in df.columns:
                    continue

                if tgt not in df.columns:
                    df[tgt] = ""

                vals = df[col].astype(str).str.strip()

                if need_lookup:
                    if tgt == "locationId":
                        df[tgt] = vals.map(lambda v: loc_index.get(_norm(v), v))
                    elif tgt == "workspaceId":
                        df[tgt] = vals.map(lambda v: ws_index.get(_norm(v), v))
                    elif tgt == "personId":
                        df[tgt] = vals.map(
                            lambda v: (list(api.people.list(email=v))[0].person_id if v else "")
                        )
                    else:
                        df[tgt] = vals
                else:
                    df[tgt] = vals

            df.to_excel(writer, index=False, sheet_name=sheet)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
