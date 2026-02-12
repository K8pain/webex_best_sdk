# Space_OdT

Deterministic, read-only Webex inventory exporter focused on CSV/JSON outputs.

## Usage

```bash
export WEBEX_ACCESS_TOKEN=...
python -m Space_OdT.cli inventory_run --out-dir .artifacts --open-report
```

## Output

- `.artifacts/exports/*.csv`
- `.artifacts/exports/*.json`
- `.artifacts/exports/status.csv`
- `.artifacts/cache.json` (optional)
- `.artifacts/report/index.html` (optional)

## Notes

- Fixed module set; no SDK crawling.
- Failures create empty exports and status rows.
- Group members can be skipped with `--skip-group-members`.


The static HTML report is generated at `.artifacts/report/index.html` (unless `--no-report` is used).
