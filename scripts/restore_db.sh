#!/usr/bin/env bash
# BilimUz — production database restore.
#
# DESTRUCTIVE: drops and recreates the target database before loading
# the backup. Requires explicit confirmation (see below) and is meant
# for disaster recovery or standing up a new environment from a known
# backup — not routine use. Never run this against a database you have
# not deliberately decided to overwrite.
#
# Usage (from the repository root):
#   ./scripts/restore_db.sh database/backups/bilimuz_2026-01-01T00-00-00Z.sql.gz
#
# What it does, in order:
#   1. Confirms the backup file exists and is a readable gzip.
#   2. Asks for explicit "yes" confirmation (skippable with --yes, for
#      scripted/documented recovery drills only).
#   3. Terminates other connections to the target database (required —
#      Postgres refuses to drop a database with active connections).
#   4. Drops and recreates the (now-empty) database.
#   5. Loads the backup into it.
#   6. Prints a basic row-count sanity check per the application's own
#      core tables — NOT a full data-integrity audit, just a quick
#      "did something load" signal. Run the application's own tests /
#      a manual smoke test afterward before trusting it in production.

set -euo pipefail

COMPOSE_FILE="docker-compose.prod.yml"
SERVICE="postgres"
DB_NAME="bilimuz"
DB_USER="postgres"

CONFIRM="no"
BACKUP_FILE=""
for arg in "$@"; do
    case "$arg" in
        --yes) CONFIRM="yes" ;;
        *) BACKUP_FILE="$arg" ;;
    esac
done

if [[ -z "$BACKUP_FILE" ]]; then
    echo "Usage: $0 <path-to-backup.sql.gz> [--yes]" >&2
    exit 1
fi
if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "Error: backup file not found: $BACKUP_FILE" >&2
    exit 1
fi
if ! gzip -t "$BACKUP_FILE" 2>/dev/null; then
    echo "Error: '$BACKUP_FILE' does not look like a valid gzip file." >&2
    exit 1
fi

echo "This will PERMANENTLY REPLACE the '${DB_NAME}' database with the"
echo "contents of: ${BACKUP_FILE}"
echo "Every row currently in '${DB_NAME}' that is not in this backup will be lost."
if [[ "$CONFIRM" != "yes" ]]; then
    read -r -p "Type 'yes' to continue: " reply
    if [[ "$reply" != "yes" ]]; then
        echo "Aborted — nothing was changed."
        exit 1
    fi
fi

echo "Recommended: back up the CURRENT database before restoring over it,"
echo "in case this restore turns out to be a mistake:"
echo "  ./scripts/backup_db.sh"
echo

echo "Terminating other connections to '${DB_NAME}'..."
docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" \
    psql -U "$DB_USER" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();"

echo "Dropping and recreating '${DB_NAME}'..."
docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" \
    psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS ${DB_NAME};"
docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" \
    psql -U "$DB_USER" -d postgres -c "CREATE DATABASE ${DB_NAME};"

echo "Loading backup..."
gunzip -c "$BACKUP_FILE" | docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" \
    psql -U "$DB_USER" -d "$DB_NAME"

echo
echo "Restore complete. Quick sanity check (row counts, not a full audit):"
docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" \
    psql -U "$DB_USER" -d "$DB_NAME" -c \
    "SELECT 'users' AS table_name, count(*) FROM users
     UNION ALL SELECT 'tests', count(*) FROM tests
     UNION ALL SELECT 'test_attempts', count(*) FROM test_attempts;" \
    || echo "(Sanity query failed — table names may differ from what this script assumes; check manually with psql.)"

echo
echo "Next: run the application's migration check to confirm the restored"
echo "schema matches what the current backend code expects:"
echo "  docker compose -f ${COMPOSE_FILE} run --rm backend alembic current"
echo "If it reports a revision older than 'alembic heads' expects, run:"
echo "  docker compose -f ${COMPOSE_FILE} run --rm backend alembic upgrade head"
