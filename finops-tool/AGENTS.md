# Instrucciones del repositorio

Lee `CLAUDE.md` antes de trabajar. `docs/DEPLOY_DEBIAN.md` es el manual de
despliegue y operación; `docs/LAB.md` describe el laboratorio (crear recursos
de prueba con Terraform, escanear, verificar con `scripts.lab_verify`, destruir).

Para cada collector AWS nuevo:
- Extiende la arquitectura de collectors existente; nunca añadas un segundo scanner.
- Usa sólo APIs de lectura (list/describe/get), con paginación completa y manejo de inventario vacío.
- Documenta las acciones IAM exactas y actualiza la política destino de mínimo privilegio
  (`TARGET_READ_ACTIONS`, `infra/policies/target-readonly.json`, `infra/modules/onboarding_role`).
- Prueba el collector real con AWS simulado y el AWS real bloqueado.
- Añade un caso al laboratorio en `infra/modules/waste_lab`.
- Preserva el aislamiento por tenant/cuenta y el AssumeRole con ExternalId.

No persistas credenciales, no registres cuerpos de AWS y no siembres datos de
prueba en despliegues. Los recursos AWS sintéticos sólo existen en tests. Nunca
ejecutes un escaneo real sin una cuenta configurada y autorizada explícitamente.
Nunca borres datos de tenants existentes como parte de desarrollo, tests o upgrades.
