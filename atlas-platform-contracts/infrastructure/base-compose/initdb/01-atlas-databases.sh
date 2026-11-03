#!/bin/bash
# Deterministic bootstrap on first boot (empty data dir): app databases +
# control-api migrations. Runs via docker-entrypoint-initdb.d (postgres image).
set -e
psql -v ON_ERROR_STOP=1 -U postgres -c "CREATE DATABASE atlas"
psql -v ON_ERROR_STOP=1 -U postgres -c "CREATE DATABASE control"
echo "applying control migrations..."
for f in /control-migrations/*.sql; do
  echo "  $(basename "$f")"
  psql -v ON_ERROR_STOP=1 -U postgres -d control -f "$f"
done
