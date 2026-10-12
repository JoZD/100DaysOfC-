# FinOps Tool — contexto e invariantes para desarrollo asistido por IA

Herramienta interna FinOps para AWS: sin agentes y de **solo lectura**. Escanea
cuentas AWS asumiendo un rol de solo lectura protegido con ExternalId, aplica
reglas deterministas (DuckDB + YAML/SQL) y muestra ahorros estimados y comandos
de remediación en un dashboard web. **La aplicación nunca ejecuta cambios en AWS.**

Se despliega con Docker Compose en una máquina Debian interna
(`docs/DEPLOY_DEBIAN.md`). Responde al usuario en español. Lee `AGENTS.md` y
`README.md` antes de cambiar algo.

## Primeros pasos en esta máquina
1. `docker compose ps` — ¿está el stack arriba? (postgres, migrate, api, web; `scanner` es opcional).
2. `docker compose run --rm api python -m scripts.admin list` — workspaces, usuarios, cuentas.
3. `curl -fsS http://127.0.0.1:${API_HOST_PORT:-8000}/health`
4. Logs: `docker compose logs --tail=100 api web scanner`.
5. Para tests ver la sección "Tests" del README (necesitan el Postgres del stack).

No leas ni muestres el contenido de `.env` (contiene secretos); para saber qué
variables existen usa `.env.example`.

## Nombre y marca
- El proyecto no tiene nombre comercial. Nombre visible: "FinOps Tool";
  identificadores: `finops` (DB, roles, contenedores), roles IAM `FinOps-ReadOnly*`
  y `FinOps-Scanner`. No introduzcas marcas, logos ni nombres de productos
  comerciales. `tests/test_production_contract.py::test_no_retired_names_anywhere`
  vigila nombres retirados.
- No añadas dependencias de servicios SaaS externos (identidad, telemetría,
  fuentes web, analítica). Todo debe funcionar en una red interna.

## AWS y seguridad
- Credenciales del scanner: cadena estándar de boto3. Opciones en
  `docs/DEPLOY_DEBIAN.md` §5 (rol de instancia EC2, perfil SSO, o credenciales
  temporales del rol `FinOps-Scanner` escritas por
  `scripts/refresh_scanner_credentials.sh` en el directorio que monta
  `docker-compose.aws-profile.yml`). Las llaves IAM de larga duración del
  operador nunca entran en los contenedores.
- Nunca guardes access keys de AWS en configuración, `.env`, imágenes, código o DB.
- La identidad del scanner tiene un único permiso: `sts:AssumeRole` sobre
  `arn:aws:iam::*:role/FinOps-ReadOnly*` (`aws_access.SOURCE_ASSUME_RESOURCE`).
  El acceso a una cuenta existe sólo si su rol confía en ese scanner y exige su
  ExternalId único. Los nombres de rol destino empiezan por `FinOps-ReadOnly`.
- Toda llamada AssumeRole lleva ExternalId. Sesiones cortas por cuenta/ejecución;
  nunca se cachean entre tenants o jobs.
- Sólo se persiste role ARN + ExternalId (tabla con RLS). Los ExternalId se
  generan en el servidor y sólo los devuelve el endpoint de setup de la cuenta.
- `services/common/aws_access.py` `TARGET_READ_ACTIONS` es la lista única de
  permisos destino; mantenla sincronizada con `infra/policies/*.json` y Terraform.
- Nunca registres credenciales, cuerpos completos de AWS ni secretos.
- Los comandos de remediación sólo se muestran. Nunca se ejecutan escrituras en cuentas destino.

## Autenticación y tenancy
- Login local, sin proveedor externo. Usuarios en la tabla `users`
  (email + hash scrypt), creados por el operador con
  `scripts.admin create-user`. `POST /auth/login` devuelve un token HS256
  firmado con `AUTH_SECRET` (emisor `finops-api`, expira en `SESSION_HOURS`).
- El web guarda el token en la cookie httpOnly `finops_session` y llama a
  FastAPI sólo desde el servidor (server components / server actions) con
  `Authorization: Bearer`. El navegador nunca habla con la API ni ve secretos.
  `API_BASE_URL` es sólo de servidor y se lee en runtime.
- Un usuario pertenece a lo sumo a un tenant (`users.tenant_id`). La API deriva
  el tenant del usuario autenticado (`services/api/tenancy.py`), nunca de un ID
  enviado por el cliente. El contexto RLS se fija por transacción.
- `POST /tenant` sólo crea el workspace del propio usuario si aún no tiene uno
  (controlado por `ALLOW_TENANT_SIGNUP`).
- `tenants` y `users` son las únicas tablas sin RLS (se leen antes de que exista
  contexto de tenant). Toda tabla de datos de tenant necesita `tenant_id` y RLS
  forzado con `NULLIF(current_setting('app.current_tenant_id', true), '')::uuid`.
- Toda consulta de tenant filtra por tenant; los joins incluyen igualdad de tenant.
- El usuario de DB en runtime (`finops_app`) no es superusuario ni tiene
  BYPASSRLS. Sólo las migraciones usan el usuario administrativo (`finops`).
- Los redirects del web son relativos (`/login`, `/dashboard`): dentro de Docker
  el servidor ve `0.0.0.0:3000` y un redirect absoluto rompería la cookie.

## Scanner y reglas
- Flujo: cuentas en DB → AssumeRole → collectors boto3 reales → DuckDB por job →
  reglas YAML/SQL declarativas → Findings → Postgres.
- DuckDB es efímero y aislado por cuenta/job.
- Ahorros y riesgo son código/SQL determinista, nunca salida de un LLM.
- Reglas en `rules/catalog/`. El SQL devuelve `resource_id` y
  `monthly_savings_usd`; las demás columnas son evidencia.
- Reemplazo por cuenta: si una recolección falla, se conservan los hallazgos
  previos de esa cuenta y las demás cuentas continúan.

## Despliegue y datos
- Soportado: Docker Compose en Linux. Postgres y la API escuchan sólo en
  127.0.0.1. El web escucha en `WEB_BIND_ADDRESS` (loopback por defecto,
  `0.0.0.0` para LAN de confianza). Nunca publiques los puertos de DB/API.
- Instalaciones nuevas: sin tenants, usuarios, cuentas ni hallazgos. Nunca
  siembres datos en despliegues reales. Los tests de DB crean y limpian sólo sus
  propios tenants/usuarios sintéticos.
- Nunca edites migraciones SQL ya aplicadas; añade nuevas. Mantén estables los
  identificadores de DB/volúmenes/Terraform una vez desplegado.
- `.env`, estado/vars de Terraform y backups están en `.gitignore` y fuera de
  los contextos de imagen.
- Los tests simulan AWS (moto/Stubber; el transporte HTTP real está bloqueado).
  Los escaneos reales son acciones del operador.
- Alcance actual: FinOps sólo AWS (EBS sin adjuntar, Elastic IPs sin asociar).
  Ingesta de costos (CUR), seguridad/compliance y otras nubes no están implementados.

## Laboratorio (infra/envs/lab)
- Sólo Terraform ejecutado por el operador crea o destruye recursos AWS, en
  cuentas de prueba autorizadas. La aplicación nunca lo hace.
- Recursos baratos, con tags `Project=finops-tool` / `Purpose=finops-lab`, y se
  destruyen al terminar (`docs/LAB.md`).
- Cada regla nueva tiene un caso positivo (y si se puede un control negativo)
  en `infra/modules/waste_lab`.
