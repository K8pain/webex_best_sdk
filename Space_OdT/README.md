# Space_OdT

Deterministic, read-only Webex inventory exporter focused on CSV/JSON outputs.

## Usage

```bash
# Option A: export the token
export WEBEX_ACCESS_TOKEN=...

# Option B: place WEBEX_ACCESS_TOKEN in a .env file
# (supported in the current folder, any parent folder, or project root)
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
