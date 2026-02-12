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

## V2.1 base (independiente de V2): softphones + bulk provision de sedes

Se añadió una base nueva en `Space_OdT/v21/` totalmente independiente de `Space_OdT/v2/`.

### Objetivo de esta base

Cubrir tareas de cierre manual/post-carga masiva para softphones, incluyendo planificación en bulk de sedes, usuarios y workspaces.

### Comando

```bash
python -m Space_OdT.cli v21_softphone_bulk_run --out-dir .artifacts --token "<WEBEX_ACCESS_TOKEN>"
```

Por defecto ejecuta **dry-run** y genera plan de acciones en:

- `.artifacts/v21/plan.csv`
- `.artifacts/v21/run_state.json`

Para modo apply (base inicial/no-op controlado):

```bash
python -m Space_OdT.cli v21_softphone_bulk_run --out-dir .artifacts --token "<WEBEX_ACCESS_TOKEN>" --v21-apply
```

### Inputs V2.1

- `.artifacts/v21/input_locations.csv`
- `.artifacts/v21/input_users.csv`
- `.artifacts/v21/input_workspaces.csv`
- `.artifacts/v21/static_policy.json`

Si faltan, el comando crea plantillas automáticamente.

### Fuera de scope (gestionado por carga masiva Control Hub)

- Alta/Modificación/Supresión usuarios
- Asignar permisos de llamadas
- Traslado de usuarios a otro CUV
- Crear Grupos de usuarios
- Añadir/Editar Ubicaciones
- Eliminar Ubicaciones
- Añadir Espacios de trabajo (Workspace)
- Modificar/Eliminar Espacios de trabajo
- Alta/Modificación contactos Webex
- Alta/Modificar los grupos de recepción de llamadas
- Agregar locuciones
- Alta/Modificar el asistente automático
- Alta/modificar las extensiones de detención de llamada
- Alta/modificar los grupos de llamadas en espera
- Alta/Modificación de Grupo de búsqueda
- Alta de Colas
- Modificación de Colas
- Agregar DDIs
- Asignar DDIs

> Nota: en ocasiones la carga masiva en Control Hub resuelve solo una parte y queda una tarea manual para cierre completo. Esta base v2.1 está pensada para soportar ese cierre manual/scriptable.

### ¿De qué archivos sale la configuración de cada caso en v2.1?

La estructura quedó así para que cada configuración sea simple de modificar:

- `Space_OdT/v21/models.py`
  - Define las entidades y etapas (`Stage`) de forma explícita.
- `Space_OdT/v21/io.py`
  - Define los contratos de entrada (cabeceras CSV) y bootstrap de plantillas.
  - Archivos de entrada:
    - `.artifacts/v21/input_locations.csv`
    - `.artifacts/v21/input_users.csv`
    - `.artifacts/v21/input_workspaces.csv`
    - `.artifacts/v21/static_policy.json`
- `Space_OdT/v21/engine.py`
  - Construye el plan de acciones (`load_plan_rows`) y ejecuta acción unitaria (`run_single_action`).
  - Persistencia de estado:
    - `.artifacts/v21/plan.csv`
    - `.artifacts/v21/run_state.json`
    - `.artifacts/v21/action_state.json`

Regla de diseño: **modificas CSV/política, no código**, salvo que quieras introducir una etapa nueva.

### UI HTML5 por botón (acción unitaria)

Ahora existe una UI local HTML5 para ejecutar una acción cada vez:

```bash
python -m Space_OdT.cli v21_softphone_ui --out-dir .artifacts --token "<WEBEX_ACCESS_TOKEN>"
```

- Abre: `http://127.0.0.1:8765`
- Cada tarjeta muestra una acción con botones:
  - **Preview**: muestra before/after de la acción antes de aplicar.
  - **Apply**: ejecuta la acción (en esta base, flujo controlado de estado para cierre manual).
- Resultado visible en JSON con:
  - `action`
  - `before`
  - `after`
  - `changed`

Esto deja claro qué está a punto de cambiar y qué cambió después.

### Estado real de implementación v2.1

No, la v2.1 todavía **no** es el 100% de toda la implementación final de endpoints productivos.
Esta entrega cubre la base independiente, la estructura de configuración, planificador de acciones y UI por botón para operación de cierre manual.
La conexión endpoint-a-endpoint a Webex para cada acción debe completarse iterativamente por etapa en siguientes incrementos.
