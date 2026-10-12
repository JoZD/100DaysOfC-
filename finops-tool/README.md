# FinOps Tool

Herramienta interna FinOps de **solo lectura** para AWS. Una identidad de
escaneo (rol de instancia, perfil SSO o el rol `FinOps-Scanner`) asume en cada
cuenta registrada un rol `FinOps-ReadOnly` protegido con ExternalId. Collectors
boto3 reales leen volúmenes EBS y Elastic IPs, reglas deterministas en
DuckDB/YAML encuentran desperdicio y un dashboard web con login local muestra
el ahorro estimado y los comandos de remediación. La aplicación **nunca**
ejecuta cambios en AWS.

```text
identidad del scanner → STS AssumeRole (ExternalId) → inventario EC2 → DuckDB + reglas
                                                                          ↓
Navegador → Next.js (cookie de sesión) → FastAPI → Postgres (aislamiento por tenant con RLS)
```

- **Abrir Claude Code en esta máquina:** `cd` a esta carpeta y ejecuta `claude`.
  `CLAUDE.md` le da el contexto y las reglas del proyecto automáticamente.
- **Desplegar / operar:** [docs/DEPLOY_DEBIAN.md](docs/DEPLOY_DEBIAN.md).
- **Laboratorio de pruebas en AWS:** [docs/LAB.md](docs/LAB.md).

## Arranque rápido

```bash
cp .env.example .env && chmod 600 .env
# Rellena POSTGRES_PASSWORD, APP_DB_PASSWORD y AUTH_SECRET con: openssl rand -hex 32
docker compose up -d --build
docker compose run --rm api python -m scripts.admin create-user --email tu@empresa.com
# Abre http://localhost:3000, inicia sesión y crea tu workspace.
```

## Qué incluye

- Backend Python 3.12: FastAPI, SQLAlchemy, boto3, pandas, DuckDB, PyJWT.
- Frontend Next.js 15 / React 19 / TypeScript / Tailwind, sin servicios externos.
- Postgres 16 con migraciones SQL y Row-Level Security por tenant.
- Login local: usuarios con contraseña (hash scrypt) gestionados por CLI; sesión
  firmada (HS256) en cookie httpOnly.
- Dos reglas: volúmenes EBS sin adjuntar y Elastic IPs sin asociar.
- Onboarding web: workspace, instrucciones del rol IAM generadas, verificación
  de AssumeRole y "Scan now". Escaneos programados opcionales (perfil `scanner`).
- Terraform: laboratorio de desperdicio, roles de solo lectura por cuenta,
  identidad del scanner y host EC2 opcional.

## Mapa del repositorio

| Ruta | Responsabilidad |
|---|---|
| `services/api/` | Login local y tokens (`auth.py`, `session.py`), API por tenant, onboarding |
| `services/common/` | Sesiones AWS temporales, verificación de identidad, documentos IAM, modelo Finding, DuckDB |
| `services/inventory_collector/` | Lecturas reales de la API EC2 y normalización |
| `services/rules_engine/` | Runner de escaneo por cuenta, reglas y persistencia |
| `services/cost_collector/` | Lector CUR futuro; no conectado |
| `scripts/` | Migraciones, admin CLI (tenants/usuarios/cuentas), diagnóstico AWS, verificación del lab |
| `rules/catalog/` | Reglas declarativas YAML/SQL |
| `migrations/` | SQL aplicado en orden por `scripts.apply_migrations` (servicio `migrate`) |
| `web/` | Dashboard, login y onboarding |
| `infra/` | Terraform y plantillas JSON exactas de las políticas IAM |
| `tests/` | Tests sintéticos; el transporte HTTP a AWS está bloqueado |

## Admin CLI

```bash
docker compose run --rm api python -m scripts.admin list
docker compose run --rm api python -m scripts.admin create-tenant --name equipo
docker compose run --rm api python -m scripts.admin create-user --email ana@empresa.com --tenant equipo
docker compose run --rm api python -m scripts.admin set-password --email ana@empresa.com
docker compose run --rm api python -m scripts.admin set-tenant --email ana@empresa.com --tenant equipo
docker compose run --rm api python -m scripts.admin delete-user --email ana@empresa.com
```

## Tests

Con el stack arriba (Postgres en `127.0.0.1:${POSTGRES_HOST_PORT}`):

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
set -a; . ./.env; set +a
export DATABASE_URL="postgresql+psycopg2://finops_app:${APP_DB_PASSWORD}@127.0.0.1:${POSTGRES_HOST_PORT:-5432}/finops"
export ADMIN_DATABASE_URL="postgresql+psycopg2://finops:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_HOST_PORT:-5432}/finops"
.venv/bin/pytest -q
.venv/bin/ruff check services scripts tests
.venv/bin/mypy services scripts
```

Los tests de DB crean y eliminan sólo sus propios tenants/usuarios sintéticos
(y una base de datos desechable para verificar migraciones). No se necesitan
credenciales AWS. Avisos conocidos: ruff UP017 (`models.py`) y BLE001
(`tests/test_rls.py`); mypy marca la falta de stubs de boto3/pandas/PyYAML.

El frontend se valida al construir su imagen (`docker compose build web` ejecuta
`next build`, que incluye la comprobación de tipos).

## Límites

Los ahorros usan precios aproximados fijos, no la factura real. CUR no está
conectado. No hay historial de hallazgos ni bloqueo de escaneos entre procesos,
y las sesiones destino duran 15 minutos.
