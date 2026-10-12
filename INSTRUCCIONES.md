# Instrucciones: llevar y levantar "FinOps Tool" en la máquina Debian del trabajo

`finops-tool/` es un clon limpio del proyecto, sin nombre comercial. Tu proyecto
original no se ha modificado.

## Qué cambió respecto al original

- **Nombre:** "FinOps Tool" en la interfaz; `finops` en los identificadores
  (base de datos `finops`, usuario `finops_app`, contenedores `finops-*`).
  Roles IAM: `FinOps-ReadOnly*` y `FinOps-Scanner`.
- **Login:** se eliminó el proveedor de identidad SaaS externo. Ahora hay
  login local con email y contraseña. Los usuarios se crean por CLI, las
  contraseñas se guardan con hash scrypt y la sesión va en una cookie httpOnly
  firmada con `AUTH_SECRET`. No hace falta ninguna cuenta externa.
- **Sin dependencias externas en runtime:** la fuente web descargada de Google
  se cambió por fuentes del sistema.
- **Lo que no se copió:** `.git`, `.env` y `web/.env.local` (secretos), estado y
  variables de Terraform, `.venv`, `node_modules`, cachés, notas personales
  (`notas`, `ESTADO.md`, `RUN.txt`, `TODO.md`, `codexreadme.md`) y los documentos
  con números de cuenta AWS y rutas personales. Se escribieron guías nuevas.
- **Nuevo:** `CLAUDE.md` (contexto para Claude), `docs/DEPLOY_DEBIAN.md`
  (manual de despliegue), `docs/LAB.md` (laboratorio genérico) y tests de login.
  Hay un test que falla si reaparece cualquier nombre antiguo.

Lo verifiqué aquí, en puertos alternativos: build de las imágenes, migraciones
desde cero, 40/40 tests y login → crear workspace → dashboard → logout en un
navegador real. Terraform pasa `validate` y `fmt`.

## 1. Llevarlo a la máquina del trabajo

El paquete está listo en `Packaged/finops-tool.tar.gz`:

```bash
scp ~/Desktop/Packaged/finops-tool.tar.gz usuario@maquina-debian:/tmp/
# en la máquina Debian:
sudo mkdir -p /opt/finops-tool && sudo chown "$USER" /opt/finops-tool
tar -xzf /tmp/finops-tool.tar.gz -C /opt/finops-tool --strip-components=1
cd /opt/finops-tool
```

(Si prefieres USB u otro medio autorizado, copia el `.tar.gz` igual.)

## 2. Instalar Docker en Debian

Sigue `docs/DEPLOY_DEBIAN.md` §2 (son unos 8 comandos). Después cierra sesión y
vuelve a entrar para que tu usuario quede en el grupo `docker`.

## 3. Configurar y levantar

```bash
cd /opt/finops-tool
cp .env.example .env && chmod 600 .env
for k in POSTGRES_PASSWORD APP_DB_PASSWORD AUTH_SECRET; do
  sed -i "s|^$k=.*|$k=$(openssl rand -hex 32)|" .env
done
# Para acceder desde otros equipos de la red: WEB_BIND_ADDRESS=0.0.0.0 en .env
docker compose up -d --build
docker compose ps
curl -fsS http://127.0.0.1:8000/health
```

## 4. Crear tu usuario y entrar

```bash
docker compose run --rm api python -m scripts.admin create-user --email tu@empresa.com
```

Te pide la contraseña (mínimo 12 caracteres). Abre `http://<ip-de-la-maquina>:3000`,
inicia sesión y crea el workspace.

## 5. Conectar AWS

Elige cómo obtiene credenciales el scanner (`docs/DEPLOY_DEBIAN.md` §5): rol
de instancia si es una EC2, perfil SSO, o el rol `FinOps-Scanner` con
credenciales temporales. Compruébalo con:

```bash
docker compose run --rm api python -m scripts.check_aws_access
```

Luego, en la web: **Accounts → Connect AWS account**, crea en la cuenta destino
el rol `FinOps-ReadOnly` que muestra la página, y pulsa **Verify connection** y
**Scan now**.

**Importante:** los roles que creaste para el proyecto original
(`CloudForge-Scanner`, `CloudForge-ReadOnly`) **no** sirven para este clon,
porque tiene otros nombres y otros ExternalId. Créalos de nuevo con los nombres
`FinOps-*` siguiendo las instrucciones de la web.

## 6. Abrir Claude en esa máquina

```bash
curl -fsSL https://claude.ai/install.sh | bash   # o: npm install -g @anthropic-ai/claude-code
cd /opt/finops-tool
claude
```

Claude lee `CLAUDE.md` automáticamente (arquitectura, reglas de seguridad y
comandos de operación) y responde en español. Para empezar, puedes pedirle:
*"Revisa el estado del stack y dime qué falta para escanear mi primera cuenta"*.

## Comandos del día a día

```bash
docker compose stop                     # parar sin borrar datos
docker compose up -d                    # arrancar
docker compose logs --tail=100 api web  # logs
docker compose run --rm api python -m scripts.admin list
```

No uses `docker compose down -v`: borra la base de datos.
