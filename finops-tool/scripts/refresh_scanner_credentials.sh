#!/usr/bin/env bash
# Mint temporary FinOps-Scanner credentials (default 12 h) from your
# operator profile and write them to the directory mounted into api/scanner
# (docker-compose.aws-profile.yml). Your long-lived keys never enter Docker.
# Containers pick up new credentials on the next scan; no restart needed.
#
#   scripts/refresh_scanner_credentials.sh          # run again when they expire
#
# Settings come from .env: SCANNER_ROLE_ARN (infra/envs/scanner_identity
# output), SCANNER_SOURCE_PROFILE (your operator profile), AWS_PROFILE_DIR,
# FINOPS_AWS_PROFILE (profile name inside the directory) and AWS_REGION.
set -euo pipefail
cd "$(dirname "$0")/.."

env_value() {  # value of KEY in .env, or the default
  local value
  value=$(grep -E "^$1=" .env 2>/dev/null | tail -n1 | cut -d= -f2- || true)
  echo "${value:-$2}"
}

role_arn=$(env_value SCANNER_ROLE_ARN "")
source_profile=$(env_value SCANNER_SOURCE_PROFILE "")
target_dir=$(env_value AWS_PROFILE_DIR "$HOME/.finops/aws")
profile=$(env_value FINOPS_AWS_PROFILE finops-scanner)
region=$(env_value AWS_REGION us-east-1)
hours=${HOURS:-12}

[[ -n "$role_arn" ]] || { echo "set SCANNER_ROLE_ARN in .env (terraform output scanner_role_arn)" >&2; exit 1; }
[[ -n "$source_profile" ]] || { echo "set SCANNER_SOURCE_PROFILE in .env (your operator profile)" >&2; exit 1; }
target_dir=${target_dir/#\~/$HOME}

umask 077
mkdir -p "$target_dir"
aws sts assume-role --profile "$source_profile" --role-arn "$role_arn" \
    --role-session-name "finops-$(id -un)" --duration-seconds $((hours * 3600)) \
    --query Credentials --output json \
  | python3 -c '
import json, os, sys
target_dir, profile, region = sys.argv[1:4]
c = json.load(sys.stdin)
key, secret, token = c["AccessKeyId"], c["SecretAccessKey"], c["SessionToken"]
files = {
    "credentials": f"[{profile}]\naws_access_key_id = {key}\n"
                   f"aws_secret_access_key = {secret}\naws_session_token = {token}\n",
    "config": f"[profile {profile}]\nregion = {region}\n",
}
for name, body in files.items():
    tmp = os.path.join(target_dir, f".{name}.tmp")
    with open(tmp, "w") as fh:
        fh.write(body)
    os.replace(tmp, os.path.join(target_dir, name))
expires = c["Expiration"]
print(f"wrote temporary {profile} credentials to {target_dir}; they expire {expires}")
' "$target_dir" "$profile" "$region"
