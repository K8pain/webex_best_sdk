# Comandos de prueba (scripts del directorio `script/`)

> Antes de probar el resto, genera usuarios dummy para el laboratorio.

## 0) Preparación de datos dummy (recomendado primero)

```bash
script/generate_dummy_users.py --domain lab.example.com --count 30 --location LAB-MAD --output tmp/dummy_users.csv
```

Formato esperado de salida CSV:

```csv
first_name,last_name,display_name,email,extension,phone_number,department,location,password
Ana,García,Ana García LAB 001,ana.garcia00123@lab.example.com,4001,+34612345678,QA,LAB-MAD,Ab1!....
```

## 1) script/clean

```bash
script/clean
script/clean --deep
script/clean org
```

**Requiere servidor/tenant:** `org` sí (usa `tests/cleanup.py` y espera credenciales + acceso Webex).

## 2) script/setup

```bash
script/setup
```

**Requiere servidor/tenant:** no directo, pero instala dependencias locales.

## 3) script/update

```bash
script/update
```

**Requiere servidor/tenant:** no, pero sí acceso a red/repos de paquetes.

## 4) script/test

```bash
script/test
script/test lint
script/test tests
script/test slow
```

**Requiere servidor/tenant:** varias pruebas de `tests/` pueden requerir token/tenant Webex válido.

## 5) script/build

```bash
script/build
script/build package
script/build docs
script/build types
script/build async
script/build methref
script/build oas
script/build apib
```

**Requiere servidor/tenant:**
- `oas` y `apib`: normalmente no tenant directo, pero sí ficheros de specs y entorno correcto.
- `docs`: herramientas docs instaladas.

## 6) script/ci

```bash
script/ci
```

**Requiere servidor/tenant:** indirectamente sí, porque ejecuta `script/test tests`.

## 7) script/console

```bash
script/console
```

**Requiere servidor/tenant:** no obligatorio para abrir consola; sí para llamadas reales al API.

## 8) script/api_ref

```bash
script/api_ref
script/api_ref force
script/api_ref forcebase
script/api_ref forcenew
script/api_ref forceauth
```

**Requiere servidor/tenant:**
- `forceauth`/`force`/`forcenew` suelen requerir auth (`developer.webex.com/.env`) y acceso web.

## 9) script/all_api_yml

```bash
script/all_api_yml
```

**Requiere servidor/tenant:** sí en partes autenticadas (`-a developer.webex.com/.env`).

## 10) script/apib2py.py

```bash
script/apib2py.py "*.apib"
script/apib2py.py "*.apib" --exclude "attachment-actions|meeting-preferences" --with-examples
script/apib2py.py "calling*.apib" --pypath wxc_sdk --pysrc -
```

**Variable real obligatoria:** `apib` (patrón o nombre de archivo APIB existente).

## 11) script/oas2py.py

```bash
script/oas2py.py --oas "open_api/*.yml" --pypath wxc_sdk
script/oas2py.py --oas "open_api/*.yml" --exclude "beta|experimental" --with-examples
script/oas2py.py --oas "open_api/*.yml" --cleanup
```

**Variable real recomendada:** `--oas` con ruta/patrón válido de specs OpenAPI.

## 12) script/all_types.py

```bash
script/all_types.py
```

**Requiere servidor/tenant:** no.

## 13) script/async_gen.py

```bash
script/async_gen.py
```

**Requiere servidor/tenant:** no.

## 14) script/method_ref.py

```bash
script/method_ref.py
```

**Requiere servidor/tenant:** no.
