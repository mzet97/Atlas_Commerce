#!/bin/bash
# Deterministic bootstrap on first boot (empty data dir): app databases +
# every service's read-model migrations. Runs via docker-entrypoint-initdb.d
# (postgres image). All files are baked into the image (see pg/Dockerfile) —
# bind mounts of repo dirs break on SELinux hosts and non-POSIX filesystems.
set -e
psql -v ON_ERROR_STOP=1 -U postgres -c "CREATE DATABASE atlas"
psql -v ON_ERROR_STOP=1 -U postgres -c "CREATE DATABASE control"
echo "applying control migrations..."
shopt -s nullglob
for f in /docker-entrypoint-initdb.d/50-control-migrations/*.sql; do
  echo "  control: $(basename "$f")"
  psql -v ON_ERROR_STOP=1 -U postgres -d control -f "$f"
done
echo "applying service read-model migrations (atlas)..."
for f in /docker-entrypoint-initdb.d/60-service-migrations/*/*.sql; do
  base=$(basename "$f")
  [ "$base" = "000_create_db.sql" ] && continue # databases created above
  echo "  ${base}"
  psql -v ON_ERROR_STOP=1 -U postgres -d atlas -f "$f"
done
