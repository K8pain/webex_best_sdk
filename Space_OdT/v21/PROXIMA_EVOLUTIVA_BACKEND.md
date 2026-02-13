# Space_OdT v2.1 · Próxima evolutiva backend (Webex Calling)

## 1) Qué vamos a construir

### Objetivo de la feature
Construir la siguiente evolutiva de backend para soportar, de extremo a extremo, el flujo de provisión de sedes Webex Calling y numeraciones desde un único proceso guiado por acciones.

### Para quién es
Para equipos de operaciones/implantación (PRE y PRO) que necesitan alta masiva y controlada de ubicaciones, PSTN y DIDs.

### Problema que resuelve
Actualmente parte del flujo está operativo (alta de sedes y alta+activación WBXC), pero faltan endpoints backend para el resto de acciones del menú:
1. listar location IDs,
2. resolver route group IDs,
3. configurar PSTN,
4. alta de numeraciones con reglas de negocio.

### Cómo funcionará
El backend expondrá acciones independientes (orquestables en pipeline) con validación de campos obligatorios, normalización de IDs base64 y auditoría de resultados por job.

### Modelo conceptual (simplificado)
- **Organization (orgId)**
  - contiene **Locations**.
- **Location (locationId)**
  - puede habilitarse para Webex Calling.
  - requiere **PSTN config** con `premiseRouteType=ROUTE_GROUP` + `premiseRouteId`.
  - permite **PhoneNumbers** (DID/TOLLFREE/MOBILE), con estado `INACTIVE` o `ACTIVE`.
- **RouteGroup (routegroupId)**
  - se resuelve por nombre de entorno (`RG_CTTI_PRE`, `RG_NDV`).

> Enfoque de diseño: mantener MVP funcional, iterar por verticales y “distill the model” (evitar lógica no esencial en esta fase).

---

## 2) Diseño de experiencia de usuario (UI preparada)

### User stories (happy path)
1. Operador selecciona “Crear y activar ubicación Webex Calling”.
2. Carga CSV/JSON y ejecuta job.
3. Consulta estado y respuesta API simplificada.
4. Continúa con “Configurar PSTN de ubicación”.
5. Finalmente ejecuta “Alta numeraciones en ubicación”.

### Flujos alternativos
- Si falta `orgId` o formato inválido, el backend rechaza antes de llamar API remota.
- Si PSTN no está configurado, alta de numeraciones devuelve error controlado con mensaje accionable.
- Si route group no existe para el entorno, se bloquea configuración PSTN con sugerencia PRE/PRO.

### Impacto en navegación UI
Menú izquierdo con acciones explícitas del proceso:
- Crear y activar ubicación Webex Calling.
- Lista IDs de ubicaciones creadas.
- Saber valor de routegroupId.
- Configurar PSTN de ubicación.
- Alta numeraciones en ubicación.

Las acciones no implementadas en backend quedan visibles como “Próximamente” (preparación frontend sin romper flujo actual).

---

## 3) Necesidades técnicas

## Definiciones funcionales por acción

### A1. Crear y activar ubicación Webex Calling
- **Campos obligatorios**: `orgId`, `announcementLanguage`, `name`, `preferredLanguage`, `timeZone`, `address1`, `city`, `state`, `postalCode`, `country`.
- **Referencia**: Enable a Location for Webex Calling.
- **Notas**:
  - `orgId` en base64 (`Y2lz...`).
  - Para locuciones en catalán: `announcementLanguage=ca_es`.
  - Resuelve dos pasos en uno: creación + activación Webex Calling.

### A2. Lista con todos los ID de ubicaciones
- **Campos obligatorios**: `orgId`.
- **Salida esperada**: `locationId` + metadatos útiles (por ejemplo cabecera existente).
- **Referencia**: List Locations Webex Calling Details.

### A3. Saber valor de routegroupId
- **Campos obligatorios**: `orgId`.
- **Salida esperada**: `id`, `name`.
- **Referencia**: Read the List of Routing Groups.
- **Regla entorno**:
  - PRE: `RG_CTTI_PRE`.
  - PRO: `RG_NDV`.

### A4. Configurar PSTN de ubicación
- **Campos obligatorios**: `locationId`, `premiseRouteType`, `premiseRouteId`.
- **Regla fija**: `premiseRouteType=ROUTE_GROUP`.
- **Referencia**: Setup PSTN Connection for a Location.
- **Dependencia**: requisito previo para alta de numeraciones.

### A5. Alta numeraciones en ubicación
- **Campos obligatorios**: `locationId`, `phoneNumbers[]`, `numberType`.
- **Recomendación operativa**: cargar DIDs con `state=INACTIVE`.
- **Referencia**: Add Phone Numbers to a location.
- **Reglas**:
  - Formato E.164, ejemplo `+34...`.
  - No subir numeraciones antes de configurar PSTN.
  - Fórmula intercom indicada por negocio: extensión `84662701` → `+34514662701`.

### Diseño técnico propuesto (backend)
- Añadir nuevos handlers REST en `ui.py` y métodos de orquestación en `engine.py`.
- Usar funciones puras para:
  - validación de payload,
  - mapeo PRE/PRO,
  - normalización de base64 IDs,
  - construcción de requests a Webex.
- Introducir Enums/tipos para estados y acciones válidas (evitar estados inválidos).
- Mantener separación “crear cliente API” vs “usar cliente API” (inyección por parámetro).

### Persistencia / estructura de datos
No se requieren tablas nuevas en esta fase (se reutiliza persistencia de jobs y resultados en disco de v2.1).
Si evoluciona a trazabilidad histórica avanzada, considerar tabla de auditoría por acción y por locationId.

### Dependencias externas
- APIs Webex Calling (Locations, Routing Groups, PSTN, Numbers).
- Token válido con scopes necesarios.

### Edge cases a documentar
- timeouts/red intermitente.
- `orgId` no decodificable.
- `locationId` inexistente.
- route group no encontrado por nombre.
- numeración inválida o duplicada.

---

## 4) Testing y seguridad

### Testing mínimo por acción
- **Unit tests**: validadores de payload, mapeos PRE/PRO, normalización de IDs.
- **Regression tests**: endpoints existentes (`/api/location-jobs`, `/api/location-wbxc-jobs`) no deben romperse.
- **Integration tests** (mock API Webex): secuencia A1 → A4 → A5.
- **E2E liviano UI**: selección de acciones, estados “Próximamente”, creación de job en acciones activas.

### Cobertura objetivo
Cobertura funcional de casos críticos y errores de negocio; no perseguir 100% lineal.

### Seguridad
- Validación estricta de input.
- No persistir tokens en logs.
- Sanitización de respuestas antes de renderizar UI.
- Control de scopes mínimos del token.

---

## 5) Plan de trabajo

### Estimación inicial
- **Total**: 4–6 días hábiles.

### Pasos sugeridos
1. **Milestone 1 (1 día)**: endpoint listar location IDs + tests.
2. **Milestone 2 (1 día)**: endpoint route groups + selector PRE/PRO + tests.
3. **Milestone 3 (1–2 días)**: endpoint PSTN location + validaciones + tests.
4. **Milestone 4 (1 día)**: endpoint numeraciones + reglas INACTIVE/E.164 + tests.
5. **Milestone 5 (1 día)**: hardening, documentación operativa y regresión.

### Riesgos principales
- Dependencias de API externa (latencia/cuotas/scopes).
- Inconsistencias de datos por entorno PRE/PRO.

### Requerido vs opcional (DoD)
- **Requerido**: acciones A2/A3/A4/A5 operativas con tests básicos.
- **Opcional**: wizard encadenado automático en UI.

---

## 6) Ripple effects

- Actualizar documentación funcional/operativa para implantación.
- Alinear comunicación con equipo de operaciones sobre orden obligatorio de pasos (PSTN antes de numeraciones).
- Revisar plantillas CSV/JSON compartidas con negocio.

---

## 7) Contexto amplio y evolución futura

### Limitaciones actuales
- Flujo parcialmente manual entre acciones.
- Dependencia fuerte de datos estáticos de entorno.

### Extensiones futuras
- Asistente guiado por etapas con validación previa (“preflight”).
- Resolución automática de routegroupId por entorno.
- Reintentos idempotentes por acción.

### Moonshots
- Pipeline declarativo completo por sede (YAML/JSON) con rollback parcial.
- Observabilidad operacional (métricas por acción, tiempo medio, tasa de rechazo).
