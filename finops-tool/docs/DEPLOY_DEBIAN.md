# Despliegue en una máquina Debian interna

Stack: `postgres` → `migrate` (aplica migraciones y termina) → `api` → `web`, más
`scanner` opcional (escaneos programados). Todo con Docker Compose.

## 1. Requisitos

- Debian 12 o 13, 2 vCPU, 4 GB RAM, 20 GB de disco.
- Salida a internet (o proxy/mirror interno) para construir las imágenes:
  Docker Hub (`python:3.12-slim`, `node:22-bookworm-slim`, `postgres:16`), PyPI y npm.
- Salida HTTPS a los endpoints de AWS (STS y EC2) para escanear.
- Sin servicios externos de identidad: el login es local.

## 2. Docker

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git openssl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"   # cierra sesión y vuelve a entrar
docker compose version
```

Si la red exige proxy, configúralo para el daemon
(`/etc/systemd/system/docker.service.d/http-proxy.conf`) y para los builds
(`~/.docker/config.json`, clave `proxies`).

## 3. Código

Copia esta carpeta a la máquina (p. ej. `/opt/finops-tool`) y entra en ella.
Opcional: `git init && git add -A && git commit -m "Initial import"` para llevar
el control de cambios en un repositorio interno.

## 4. Configuración (`.env`)

```bash
cp .env.example .env
chmod 600 .env
for k in POSTGRES_PASSWORD APP_DB_PASSWORD AUTH_SECRET; do
  sed -i "s|^$k=.*|$k=$(openssl rand -hex 32)|" .env
done
```

Variables importantes:

| Variable | Uso |
|---|---|
| `POSTGRES_PASSWORD` | Usuario administrativo de la DB (sólo migraciones) |
| `APP_DB_PASSWORD` | Usuario de la aplicación (`finops_app`, sin bypass de RLS) |
| `AUTH_SECRET` | Firma las sesiones del dashboard. Cambiarlo cierra todas las sesiones |
| `SESSION_HOURS` | Duración de la sesión (por defecto 12) |
| `WEB_BIND_ADDRESS` / `WEB_PORT` | `127.0.0.1` sólo esta máquina; `0.0.0.0` para la LAN |
| `POSTGRES_HOST_PORT` / `API_HOST_PORT` | Puertos de loopback, por si 5432/8000 están ocupados |
| `COOKIE_SECURE` | `true` sólo si se sirve por HTTPS (proxy TLS) |
| `COMPOSE_PROFILES` | `scanner` activa los escaneos programados |
| `ALLOW_TENANT_SIGNUP` | Un usuario sin workspace puede crearlo desde la web |

## 5. Credenciales AWS del scanner

La API ("Verify connection", "Scan now") y el servicio `scanner` usan la cadena
estándar de boto3. Elige **una** opción. Nunca pongas access keys en `.env`.

**A. La máquina es una EC2 con rol de instancia.** No configures nada. Requiere
IMDSv2 con `http_put_response_hop_limit = 2` para que Docker alcance el IMDS.
El rol necesita sólo `sts:AssumeRole` sobre `arn:aws:iam::*:role/FinOps-ReadOnly*`
(`infra/policies/source-identity.json`).

**B. Perfil SSO (IAM Identity Center).** En `.env`:

```bash
COMPOSE_FILE=docker-compose.yml:docker-compose.aws-profile.yml
FINOPS_AWS_PROFILE=<nombre del perfil SSO>
AWS_PROFILE_DIR=/home/<usuario>/.aws
HOST_UID=1000        # id -u
HOST_GID=1000        # id -g
```

Luego `aws sso login --profile <perfil>` cuando caduque y `docker compose up -d`.
El rol SSO debe poder hacer `sts:AssumeRole` sobre `FinOps-ReadOnly*`.

**C. Usuario IAM del operador, sin SSO.** Crea una vez el rol `FinOps-Scanner`:

```bash
cd infra/envs/scanner_identity
cp terraform.tfvars.example terraform.tfvars   # perfil del operador + número de cuenta
terraform init && terraform apply              # salida: scanner_role_arn
```

En `.env`:

```bash
COMPOSE_FILE=docker-compose.yml:docker-compose.aws-profile.yml
FINOPS_AWS_PROFILE=finops-scanner
AWS_PROFILE_DIR=/home/<usuario>/.finops/aws
HOST_UID=1000
HOST_GID=1000
SCANNER_ROLE_ARN=arn:aws:iam::<cuenta>:role/FinOps-Scanner
SCANNER_SOURCE_PROFILE=<perfil del operador>
```

Y cada 12 h: `scripts/refresh_scanner_credentials.sh` (escribe credenciales
temporales en `AWS_PROFILE_DIR`; las llaves del operador no entran en Docker).

**D. Credenciales temporales de la shell** (pruebas puntuales):
`COMPOSE_FILE=docker-compose.yml:docker-compose.aws-env.yml` y exporta
`AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/AWS_SESSION_TOKEN` antes de `up`.

Comprobación:

```bash
docker compose run --rm api python -m scripts.check_aws_access
```

## 6. Arranque

```bash
docker compose up -d --build
docker compose ps                       # migrate "exited (0)", api "healthy", web "running"
curl -fsS http://127.0.0.1:8000/health  # {"status":"ok"}
```

## 7. Primer usuario y workspace

```bash
docker compose run --rm api python -m scripts.admin create-user --email tu@empresa.com
```

Pide la contraseña (mínimo 12 caracteres). Abre `http://<host>:3000`, inicia
sesión y crea el workspace. Usuarios adicionales del mismo equipo:

```bash
docker compose run --rm api python -m scripts.admin list
docker compose run --rm api python -m scripts.admin create-user --email otra@empresa.com --tenant <workspace>
```

Para que sólo el operador cree workspaces: `ALLOW_TENANT_SIGNUP=false`, luego
`create-tenant --name <workspace>` y `create-user ... --tenant <workspace>`.

## 8. Conectar cuentas AWS

Dashboard → **Accounts → Connect AWS account**. La página de la cuenta muestra
el rol `FinOps-ReadOnly` exacto (trust con la identidad del scanner y el
ExternalId, permisos `ec2:DescribeRegions/Volumes/Addresses`). Alguien con
permisos en esa cuenta lo crea (CloudShell, CLI o CloudFormation). Después
**Verify connection** y **Scan now**.

## 9. Escaneos programados

`COMPOSE_PROFILES=scanner` en `.env` y `docker compose up -d`. Escanea todas las
cuentas verificadas cada `SCAN_INTERVAL_SECONDS` (6 h por defecto):

```bash
docker compose logs -f scanner
docker compose run --rm api python -m services.rules_engine.runner --tenant <ws> --account <cuenta>
```

## 10. Acceso desde la LAN

`WEB_BIND_ADDRESS=0.0.0.0` y `docker compose up -d web`. Abre el puerto
`WEB_PORT` sólo a la red interna (p. ej. `sudo ufw allow from 10.0.0.0/8 to any port 3000`).
Postgres y la API siguen en loopback. Si pones un proxy TLS delante, usa
`COOKIE_SECURE=true`.

## 11. Parar, actualizar, backup

```bash
docker compose stop                     # parar sin borrar datos
docker compose up -d --build            # tras actualizar el código (migra solo)
docker compose exec -T postgres pg_dump -U finops -Fc finops > backup-$(date +%F).dump
docker compose exec -T postgres pg_restore -U finops -d finops --clean < backup.dump
```

**Nunca** `docker compose down -v` salvo que quieras borrar la base de datos.

## 12. Problemas frecuentes

| Síntoma | Causa / solución |
|---|---|
| `set AUTH_SECRET in .env` al arrancar | Falta en `.env` (mínimo 32 caracteres) |
| Login vuelve siempre a `/login` | Sesión caducada, `AUTH_SECRET` cambió, o `COOKIE_SECURE=true` sobre HTTP |
| "Invalid email or password" | `scripts.admin list` / `set-password` |
| Verify falla en etapa `source` | Sin credenciales AWS en los contenedores (§5) |
| Verify falla en `assume_role` | Trust/ExternalId/nombre de rol incorrectos en la cuenta destino |
| `ExpiredToken` | Renueva credenciales (`refresh_scanner_credentials.sh` o `aws sso login`) |
| Puerto ocupado | Cambia `POSTGRES_HOST_PORT`, `API_HOST_PORT` o `WEB_PORT` |
