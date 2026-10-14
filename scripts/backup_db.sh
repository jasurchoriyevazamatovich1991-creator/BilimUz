#!/usr/bin/env bash
# BilimUz — production database backup.
#
# No backup automation existed before this sprint (database/backups/ was
# empty, .gitkeep only — confirmed by direct inspection). This script is
# new, not a wrapper around a pre-existing tool.
#
# Runs `pg_dump` INSIDE the running postgres container (docker-compose.prod.yml's
# `postgres` service) via `docker compose exec`, so it never needs direct
# network access to a database that — correctly — has no published port.
# Writes to ./database/backups/, which docker-compose.prod.yml mounts
# into the postgres container at /backups, so pg_dump can also write
# straight there without an extra copy step.
#
# Usage (from the repository root):
#   ./scripts/backup_db.sh
#
# Produces: database/backups/bilimuz_YYYY-MM-DDTHH-MM-SSZ.sql.gz
#
# This script only READS from the database (pg_dump is non-destructive).
# It never drops, truncates, or modifies anything.

set -euo pipefail

COMPOSE_FILE="docker-compose.prod.yml"
SERVICE="postgres"
DB_NAME="bilimuz"
DB_USER="postgres"
BACKUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/database/backups"
TIMESTAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
OUT_FILE="bilimuz_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "Backing up '${DB_NAME}' from the '${SERVICE}' service to ${BACKUP_DIR}/${OUT_FILE} ..."

docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" \
    pg_dump -U "$DB_USER" -d "$DB_NAME" --format=plain \
    | gzip > "${BACKUP_DIR}/${OUT_FILE}"

SIZE="$(du -h "${BACKUP_DIR}/${OUT_FILE}" | cut -f1)"
echo "Done: ${BACKUP_DIR}/${OUT_FILE} (${SIZE})"
echo
echo "Verify integrity (does not restore anything, just checks the gzip isn't truncated/corrupt):"
echo "  gzip -t '${BACKUP_DIR}/${OUT_FILE}' && echo OK"
echo
echo "This script does NOT delete old backups or manage retention — see"
echo "docs/Deployment/PRODUCTION.md's 'Backup scheduling' section for a"
echo "cron-based retention recommendation (a manual operational step,"
echo "not something this sprint automates)."
