#!/usr/bin/env bash
set -euo pipefail
args=(gunicorn --bind "0.0.0.0:${PORT:-10000}" --workers "${WEB_CONCURRENCY:-2}"
  --access-logfile - --access-logformat "%(m)s %(U)s %(s)s %(D)s" app:app)

if [[ -n "${OTEL_EXPORTER_OTLP_ENDPOINT:-}" ]]; then
  export OTEL_SERVICE_NAME="${OTEL_SERVICE_NAME:-recipe-box}"
  export OTEL_TRACES_EXPORTER="${OTEL_TRACES_EXPORTER:-otlp}"
  export OTEL_METRICS_EXPORTER="${OTEL_METRICS_EXPORTER:-otlp}"
  export OTEL_LOGS_EXPORTER="${OTEL_LOGS_EXPORTER:-none}"
  export OTEL_PYTHON_FLASK_EXCLUDED_URLS="/auth/.*,healthz,readyz"
  export OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SANITIZE_FIELDS="authorization,cookie,set-cookie,x-csrf-token,location"
  exec opentelemetry-instrument "${args[@]}"
fi
exec "${args[@]}"
