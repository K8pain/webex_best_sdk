from __future__ import annotations

import json
from pathlib import Path

from SpaceOdT import cli


def test_main_fails_when_token_missing(capsys, monkeypatch):
    monkeypatch.delenv("WEBEX_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("WEBEX_TOKEN", raising=False)
    exit_code = cli.main(["export-all", "--out-dir", ".tmp-artifacts"])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Missing Webex token" in output


def test_run_exports_generates_files_and_report(tmp_path: Path):
    out_dir = tmp_path / "artifacts"

    results = cli.run_exports(
        out_dir=out_dir,
        no_report=False,
        skip_group_members=False,
        env={"WEBEX_ACCESS_TOKEN": "fake-token"},
    )

    assert len(results) == len(cli.FIXED_MODULES)
    for module in cli.FIXED_MODULES:
        assert (out_dir / f"{module}.json").exists()

    report_path = out_dir / cli.DEFAULT_REPORT_NAME
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["total_modules"] == len(cli.FIXED_MODULES)


def test_skip_group_members_and_no_report(tmp_path: Path):
    out_dir = tmp_path / "artifacts"

    results = cli.run_exports(
        out_dir=out_dir,
        no_report=True,
        skip_group_members=True,
        env={"WEBEX_ACCESS_TOKEN": "fake-token"},
    )

    modules = [result.module for result in results]
    assert "group_members" not in modules
    assert not (out_dir / cli.DEFAULT_REPORT_NAME).exists()


def test_summary_line_format(tmp_path: Path):
    out_dir = tmp_path / "artifacts"
    result = cli.ModuleExportResult(
        module="people",
        result="ok",
        count=3,
        file_paths=(str(out_dir / "people.json"),),
    )

    summary = cli.format_summary_line(result)

    assert summary.startswith("people -> ok -> 3 ->")
