# v21 probe troubleshooting (real token run)

Fecha: 2026-02-14

## Alcance
- Se ejecutaron los `action_*.py` en `--mode probe` con token real.
- Total scripts con `SPEC`: 19.
- Script omitido por no exponer `SPEC`: `action_alta_sedes_wbxc.py`.
- Reporte crudo generado localmente durante la ejecución (no versionado en git): `actions/logs/probe_real_token_report.json`.

## Resultado rápido
- Exits `0`: 14
- Exits `1`: 5 (`action_call_pickup_group.py`, `action_group_assignment.py`, `action_internal_extensions_sbc.py`, `action_interplatform_dial_plan.py`, `action_nominal_users.py`)

## Errores detectados (no conexión)

### 1) IDs dummy con tipo inválido en Resource ID (plural)
Síntoma repetido:
- `LOCATIONS is not a valid Webex Resource Type`
- `WORKSPACES is not a valid Webex Resource Type`

Impacto:
- Afecta probes que usan `location_id` o `workspace_id` dummy con prefijos no válidos en el ID Webex.

Propuesta:
- Estandarizar valores dummy en formato de ID válido (`LOCATION`, `PEOPLE`, etc.) y no usar IDs con tipo plural.
- Usar `actions/v21_dummy_vars.json` como plantilla base de `--vars`.

### 2) Endpoints que devuelven "No static resource ..."
Síntoma repetido en varios scripts:
- `No static resource hydra/v1/telephony/config/...`

Interpretación práctica:
- Puede ocurrir por endpoint fuera de contrato para el tenant/token o por path legacy no habilitado en ese entorno.

Propuesta:
- Revisar paridad endpoint por endpoint en `actions/vars_mapping.md` y mover los probes a rutas confirmadas en tenant actual.
- Mantener `acceptable_statuses` para 404 en probe cuando el objetivo sea diagnóstico de existencia.

### 3) Método HTTP no soportado en probe de grupos
Síntoma:
- `405` en `probe_membership_add` de `action_group_assignment.py`.

Propuesta:
- Cambiar el probe de alta de membresía de `POST` a flujo de lectura (`GET`) o usar el método soportado por el endpoint real del tenant.

### 4) Permiso insuficiente (403) en números de usuario
Síntoma:
- `403 Forbidden` en `action_nominal_users.py` (`probe_user_numbers_missing`).

Propuesta:
- Validar scopes del token para telephony config antes del lote.
- Agregar precheck explícito de scopes/recurso en el runner y marcar como `permission_blocked`.

## Siguiente paso sugerido
1. Reintentar probes usando el archivo `actions/v21_dummy_vars.json`.
2. Corregir probes con 405/404 estructural.
3. Repetir corrida y comparar contra el reporte crudo local recién generado.
