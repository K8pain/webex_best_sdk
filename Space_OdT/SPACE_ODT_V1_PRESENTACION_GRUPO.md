# Space_OdT v1 — Documento de presentación (audiencia técnica intermedia)

> Alcance: **solo v1** (inventario determinista de lectura para Webex). No cubre v2 ni v2.1.

## 1) Qué estamos construyendo

### Qué es
Space_OdT v1 es un **exportador de inventario Webex en modo read-only**, orientado a generar artefactos **CSV/JSON** de forma determinista y repetible.

### Para quién es
- Equipos de operación/ingeniería de voz y colaboración.
- Equipos de migración, auditoría o gobierno de configuración.
- Soporte técnico que necesita snapshots comparables del estado real.

### Problema que resuelve
- Evitar extracciones manuales y no trazables.
- Unificar el inventario de configuración en archivos procesables.
- Generar una base fiable para diagnóstico, reporting y automatizaciones posteriores.

### Cómo funciona (modelo operativo)
1. Ejecuta módulos base (personas, grupos, ubicaciones, licencias, etc.).
2. Construye cache de entidades para resolver IDs automáticamente.
3. Ejecuta artefactos v1 (llamadas de detalle/lectura por entidad).
4. Persistencia en `exports/*.csv|json` + `status.csv|json` + reporte HTML opcional.

### Conceptos principales y relaciones
- **ModuleSpec**: define extracción base por dominio (lista + detalle opcional).
- **ArtifactSpec**: define métodos de recuperación v1 y sus dependencias de parámetros.
- **ParamSource**: mapea de qué módulo/campo se obtiene cada ID.
- **StatusRecorder**: deja trazabilidad de éxito/error por método ejecutado.

### Notas de diseño (MVP)
- Diseño e implementación en paralelo ya materializados en una versión utilizable.
- “Distilling the model”: v1 evita introspección dinámica y usa manifiesto fijo para reducir complejidad.
- Priorización tipo MVP: foco en extracción estable y verificable antes que cobertura total de endpoints.

---

## 2) Diseño de experiencia de usuario (operador)

### Historias de usuario (happy path)
- Como operador, lanzo `inventory_run` con token y obtengo un inventario completo en CSV/JSON.
- Como analista, abro el reporte HTML para ver conteos por módulo y errores por método.
- Como equipo técnico, uso `status.csv` para validar qué partes fueron exitosas o fallaron.

### Flujos alternativos
- Sin token explícito: se puede usar variable de entorno o `.env`.
- Si falla un módulo o artefacto: se genera archivo vacío del módulo y el error queda en `status`.
- Si ciertos endpoints de persona devuelven 4003 (usuario sin entitlement): se omiten esas entidades y el proceso continúa.

### Estructura de la UI (v1)
- No hay UI web interactiva; la UX es de CLI + reporte estático HTML.
- `--open-report` abre automáticamente el reporte al finalizar.

### Wireframe mental rápido
- **Entrada**: token + `--out-dir`.
- **Proceso**: extracción base → artefactos v1 → escritura de estado.
- **Salida**: ficheros + reporte de ejecución.

---

## 3) Necesidades técnicas

### Detalles que dev necesita conocer
- Runtime: Python.
- Orquestación por catálogo de módulos (`MODULE_SPECS`) y manifiesto v1 (`V1_ARTIFACT_SPECS`).
- Lógica determinista: sin crawling ni descubrimiento dinámico de SDK.

### Base de datos
- v1 **no introduce tablas** ni migraciones; trabaja contra APIs Webex y filesystem local.

### Diseño técnico clave
- Se prioriza función pura/pequeña para transformar filas y resolver parámetros.
- Separación de responsabilidades:
  - resolver rutas/métodos,
  - ejecutar con kwargs soportados,
  - normalizar salida,
  - persistir CSV/JSON,
  - registrar estado.
- Inyección de dependencia implícita: `run_exports(api, settings)` recibe API ya creado.

### Dependencias externas
- SDK de Webex del propio repositorio (`wxc_sdk`).
- Acceso a API Webex (token válido).

### Edge cases documentados en implementación
- Error 4003 en endpoints de persona: se trata como caso esperable y se continúa.
- Métodos con error quedan reflejados en `status` sin tumbar toda la ejecución.

---

## 4) Testing y seguridad

### Qué está confirmado hoy
- Parser CLI acepta `inventory_run` y `--token`.
- `inventory_run` pasa correctamente el token a la creación del cliente API.
- El filtrado por `required_field` en resolución de kwargs funciona.
- El runner de artefactos ignora correctamente errores 4003 y sigue con el resto.

### Tipos de test necesarios/recomendados
- Unit tests (actuales): kwargs, manejo de errores, parser CLI.
- Regression tests: estabilidad de columnas/salidas por módulo.
- Integración (recomendado): ejecución real contra tenant sandbox controlado.

### Seguridad para ship
- Operación read-only (sin writes a Webex).
- Token de acceso como secreto operativo: usar variable de entorno/.env y rotación normal.
- Validar control de artefactos exportados por contener datos operativos sensibles.

---

## 5) Plan de trabajo (presentación + operación)

### Estimación de adopción interna (v1)
- Preparación entorno + token: 0.5 día.
- Primera ejecución y revisión de outputs: 0.5 día.
- Ajuste de pipeline/reporting interno: 1–2 días.
- Total típico: **2–3 días laborables**.

### Milestones sugeridos
1. **M1**: primera corrida v1 exitosa con `status` limpio en entorno de prueba.
2. **M2**: validación de inventario con equipo de operación.
3. **M3**: automatización recurrente (job programado + retención de artefactos).

### Riesgos y mitigaciones
- Riesgo principal: permisos/token insuficiente → mitigación: revisión de scopes y tenant de pruebas.
- Riesgo de volumen/duración: alto número de entidades → mitigación: particionar análisis por artefacto.
- Riesgo de interpretación: datos crudos complejos (`raw_json`) → mitigación: vistas derivadas internas.

### Definition of Done (v1 operativo)
**Requerido**
- Ejecución completa sin caída global.
- Exportes CSV/JSON generados.
- `status.csv/json` consumible.

**Opcional**
- Reporte HTML publicado en canal interno.
- Job recurrente con versionado de snapshots.

---

## 6) Ripple effects (fuera del código)

- Documentar ubicación estándar de artefactos (`.artifacts/exports`).
- Alinear con operaciones cómo clasificar errores esperables vs incidentes.
- Definir política de retención y acceso a datos exportados.
- Comunicar a stakeholders que v1 es inventario de lectura (no aprovisionamiento).

---

## 7) Contexto amplio y evolución

### Limitaciones actuales de v1
- Cobertura basada en manifiesto fijo (si falta endpoint, no aparece solo).
- No ejecuta acciones de remediación/aplicación.
- Dependencia del estado de permisos del token.

### Extensiones futuras posibles
- Capas de “insights” sobre el inventario (detección de anomalías).
- Diff entre snapshots para cambios de configuración.
- Conectores a BI o data lake para análisis histórico.

### Moonshot ideas
- Motor de cumplimiento declarativo: “estado objetivo” vs “estado actual” sobre inventario.
- Sistema de score de riesgo operativo por módulo/ubicación/cola.

---

## Inventario confirmado “a día de hoy” (v1)

Además de módulos base (`people`, `groups`, `locations`, `licenses`, `workspaces`, etc.), v1 tiene confirmado el soporte de artefactos de recuperación para:

- **Calling locations**: listado y detalle.
- **Grupos/Licencias/Workspaces**: miembros, usuarios asignados, capacidades.
- **Auto attendants**: listado, detalle, anuncios, forwarding.
- **Hunt groups**: listado, detalle, forwarding.
- **Call queues**: listado, detalle, settings, agentes, forwarding.
- **Virtual lines**: listado, detalle, dispositivos asignados, números disponibles.
- **Virtual extensions**: extensiones/rangos y sus detalles.
- **Person settings**: números, permisos in/out, access codes, digit patterns, transfer numbers.
- **Available numbers por persona/workspace/virtual line**: variantes available/primary/secondary y casos específicos (call forward, intercept, ecbn, fax).

Esto representa la base funcional confirmada por el manifiesto de artefactos v1 y el runner de exportación actual.
