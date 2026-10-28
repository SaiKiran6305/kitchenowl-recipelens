#!/usr/bin/env bash
set -euo pipefail

JWT_SECRET_KEY=${JWT_SECRET_KEY:-}
if [[ ${#JWT_SECRET_KEY} -lt 32 || "$JWT_SECRET_KEY" == "PLEASE_CHANGE_ME" ]]; then
  echo 'Set JWT_SECRET_KEY to a random secret of at least 32 characters.' >&2
  exit 1
fi
if [[ "${RAILWAY_VOLUME_MOUNT_PATH:-}" != /data ]]; then
  echo 'Attach a persistent Railway volume at /data before starting this service.' >&2
  exit 1
fi
export STORAGE_PATH=/data
mkdir -p "$STORAGE_PATH/upload"
flask db upgrade
if [[ "${SKIP_UPGRADE_DEFAULT_ITEMS:-false}" != true ]]; then
  python upgrade_default_items.py
fi

# One process owns the SQLite database and in-process Socket.IO sessions.
# The existing entrypoint uses a uWSGI socket; Railway needs an HTTP listener.
exec uwsgi --ini wsgi.ini --http "0.0.0.0:${PORT:-8080}" \
  --gevent 100 --processes 1 --max-fd 65536 \
  --static-map /=/var/www/web/kitchenowl \
  --route '^/(?!api)(?!mcp)[^\.]*$ static:/var/www/web/kitchenowl/index.html'
