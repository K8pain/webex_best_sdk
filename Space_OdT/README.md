# Space_OdT

Deterministic, read-only Webex inventory exporter focused on CSV/JSON outputs.

## V1 behavior

- Uses a fixed method manifest only (no crawling, no SDK introspection).
- Executes retrieval-only methods (`list/details/read/get/members/capabilities/count/status/errors/history/summary/available_numbers.*`).
- Resolves IDs automatically from prior exports (`people`, `groups`, `locations`, `workspaces`, `virtual_lines`, etc.).
- Writes one status record per executed artifact method in `status.csv/json`.

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

The static HTML report shows all modules in a single modern dashboard view (inventory + method status table in the same plane).
