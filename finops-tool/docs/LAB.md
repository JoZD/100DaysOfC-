# Laboratorio: comprobar un escaneo real contra recursos de prueba

Crea recursos AWS baratos y "desperdiciados" en una **cuenta de pruebas
autorizada**, escanéala con la herramienta, verifica los hallazgos y destruye
todo. Sólo Terraform ejecutado por ti crea o borra recursos; la aplicación nunca.

Necesitas: Terraform ≥ 1.7, AWS CLI v2, un perfil con permisos de administración
en la cuenta de pruebas (en estos ejemplos `lab-admin`) y el stack corriendo con
credenciales de scanner configuradas (`docs/DEPLOY_DEBIAN.md` §5).

## 1. Registrar la cuenta de pruebas en la web

Dashboard → **Accounts → Connect AWS account** → nombre (p. ej. `lab-a`) y número
de cuenta. La página siguiente muestra el ExternalId y el rol
`FinOps-ReadOnly` a crear (CloudShell, CLI o CloudFormation). Créalo en la
cuenta de pruebas y pulsa **Verify connection**.

Alternativa con Terraform (sólo para cuentas que administras tú):

```bash
cd infra/envs/member_account
cp terraform.tfvars.example accounts/lab-a.tfvars   # rellena perfil, cuenta, ExternalId, host_role_arn
terraform init
terraform workspace new lab-a || terraform workspace select lab-a
terraform apply -var-file=accounts/lab-a.tfvars
```

## 2. Crear los recursos de prueba

```bash
cd infra/envs/lab
cp terraform.tfvars.example accounts/lab-a.tfvars   # aws_profile = "lab-admin", expected_account_id = "<CUENTA>"
terraform init
terraform workspace new lab-a || terraform workspace select lab-a
terraform apply -var-file=accounts/lab-a.tfvars
```

Crea volúmenes EBS sin adjuntar y Elastic IPs sin asociar (casos positivos) y
una EIP asociada como control negativo. La salida `lab` lista lo esperado.

## 3. Escanear

En la web, **Scan now** en la cuenta, o por CLI:

```bash
docker compose run --rm api python -m services.rules_engine.runner --tenant <workspace> --account lab-a
```

## 4. Verificar

```bash
terraform -chdir=infra/envs/lab output -json lab > /tmp/lab-a.json
docker compose run --rm -T api python -m scripts.lab_verify --tenant <workspace> --account lab-a < /tmp/lab-a.json
```

Pasa si cada recurso esperado tiene su hallazgo con el ahorro esperado y ningún
control aparece marcado. Otros recursos que ya existían en la cuenta se listan
como `other` pero no hacen fallar la comprobación.

## 5. Destruir

```bash
cd infra/envs/lab && terraform workspace select lab-a
terraform destroy -var-file=accounts/lab-a.tfvars
```

Escanea de nuevo: los hallazgos del laboratorio desaparecen.

## Problemas frecuentes

- `ExpiredToken`: credenciales temporales del scanner caducadas →
  `scripts/refresh_scanner_credentials.sh` (o `aws sso login`).
- `AccessDenied` en AssumeRole: el trust del rol no nombra exactamente la
  identidad del scanner, el ExternalId no coincide, o el rol no empieza por
  `FinOps-ReadOnly`.
- Sin VPC por defecto en la región: `create_controls = false` en el tfvars.
