#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${MIGRATION_DATABASE_URL:-}" ]]; then
  export DATABASE_URL="$MIGRATION_DATABASE_URL"
fi
exec flask --app app db upgrade
