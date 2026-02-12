# Space_OdT

Deterministic, read-only Webex inventory exporter focused on CSV/JSON outputs.

## V1 behavior

- Uses a fixed method manifest only (no crawling, no SDK introspection).
- Executes retrieval-only methods (`list/details/read/get/members/capabilities/count/status/errors/history/summary/available_numbers.*`).
- Resolves IDs automatically from prior exports (`people`, `groups`, `locations`, `workspaces`, `virtual_lines`, etc.).
- Writes one status record per executed artifact method in `status.csv/json`.

## Usage

```bash
# Option A: pass token directly (highest priority)
python -m Space_OdT.cli inventory_run --token "<WEBEX_ACCESS_TOKEN>" --out-dir .artifacts --open-report

# Option B: export the token
export WEBEX_ACCESS_TOKEN=...
python -m Space_OdT.cli inventory_run --out-dir .artifacts --open-report

# Option C: place WEBEX_ACCESS_TOKEN in a .env file
# (supported in the current folder, any parent folder, or project root)
python -m Space_OdT.cli inventory_run --out-dir .artifacts --open-report

# Windows/PowerShell alternative (script path invocation)
python Space_OdT\cli.py inventory_run --out-dir .\.artifacts\ --open-report
```

## Output

- `.artifacts/exports/*.csv`
- `.artifacts/exports/*.json`
- `.artifacts/exports/status.csv`
- `.artifacts/cache.json` (optional)
- `.artifacts/report/index.html` (optional)

The static HTML report highlights the new V1 artifacts in a dedicated section so new coverage is visible quickly.

## V2 bulk softphone provisioning (CLI)

V2 adds an async bulk runner for provisioning existing users as softphones using V1 inventory as lookup cache.

### Inputs

- `.artifacts/v1_inventory/*` from V1 inventory export (used for `email -> person_id`, location and queue resolution).
- `.artifacts/v2/input_softphones.csv` with at least: `user_email`, `calling_license_id`, (`location_id` or `location_name`), (`extension` or `phone_number`).
- `.artifacts/v2/static_policy.json` with global defaults for optional calling features.

### Run

```bash
python -m Space_OdT.cli v2_bulk_run --out-dir .artifacts --concurrent-requests 20
```

Optional flags:

- `--only-failures`: re-run records failed in previous `run_state.json`.
- `--debug-har`: writes `.artifacts/v2/http.har` for HTTP-level troubleshooting.
- `--decisions-file`: JSON con decisiones por etapa para ejecución no interactiva (`yes`, `no`, `yesbut <archivo>`).

### Interactive approvals

En modo normal, antes de cada etapa se solicita confirmación:

- `yes`: aplicar etapa completa
- `no`: saltar etapa
- `yesbut <archivo>`: aplicar etapa con override específico por usuario (CSV/JSON con `user_email`)

### Outputs

- `.artifacts/v2/run_state.json`
- `.artifacts/v2/failures.csv`
- `.artifacts/v2/report.html` (estado anterior/actual por acción)
- `.artifacts/v2/changes.log` (detallado técnico en JSON lines)
- `.artifacts/v2/http.har` (only with `--debug-har`)
