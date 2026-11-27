#!/usr/bin/env bash
# Bring the production database (Neon) up to date with this checkout:
#   1. back it up to dist/neon-backup-<date>.dump (restorable with pg_restore)
#   2. apply database migrations
#   3. replace the trade tables with the local gold data (countries, products,
#      markets, suppliers, sea routes); user data is never touched
#   4. embed new or changed products for HS-code search (Gemini embedding quota)
#   5. print the database size (Neon free plan: 512 MB)
#
#   make neon-update                 everything
#   SKIP_DATA=1 make neon-update     backup + migrations only
#
# The connection string is read from deploy/ec2/.env.deploy (PROD_DATABASE_URL), or asked
# for (hidden input) when it isn't saved there. It is never printed. psql runs from the
# local stack's Postgres image; pg_dump from the official image matching the server's
# major version (pg_dump refuses servers newer than itself; Neon runs a newer Postgres).
set -euo pipefail
cd "$(dirname "$0")/.."

CONF=deploy/ec2/.env.deploy
PG_IMAGE=pgvector/pgvector:pg16
# shellcheck disable=SC1090
[ -f "$CONF" ] && source "$CONF"
if [ -z "${PROD_DATABASE_URL:-}" ]; then
  # Not saved in the file: ask for it (input hidden, used for this run only).
  read -rsp "Paste the Neon connection string (input hidden), then Enter: " PROD_DATABASE_URL
  echo
  PROD_DATABASE_URL="${PROD_DATABASE_URL//\'/}"   # tolerate pasted quotes
  PROD_DATABASE_URL="${PROD_DATABASE_URL//\"/}"
  case "$PROD_DATABASE_URL" in
    postgres://*|postgresql://*|postgresql+*://*) ;;
    *) echo "That doesn't look like a Postgres connection string" >&2; exit 1 ;;
  esac
fi

# Neon gives a libpq URL; strip any SQLAlchemy driver prefix for pg_dump/psql.
LIBPQ_URL="postgresql://${PROD_DATABASE_URL#*://}"
export LIBPQ_URL
pg() { docker run --rm -i -e LIBPQ_URL "$PG_IMAGE" "$@"; }

echo "==> Checking the connection"
server_num=$(pg sh -c 'psql "$LIBPQ_URL" -Atc "show server_version_num"')
server_major=$(( server_num / 10000 ))
echo "    Postgres $server_major"

mkdir -p dist
backup="dist/neon-backup-$(date +%Y%m%d-%H%M%S).dump"
echo "==> Backing up to $backup"
# pg_dump must be at least as new as the server, so use the server's own major version.
docker run --rm -e LIBPQ_URL "postgres:${server_major}-alpine" \
  sh -c 'pg_dump "$LIBPQ_URL" --format=custom --no-owner --no-privileges' > "$backup.part" \
  || { rm -f "$backup.part"; echo "Backup failed; stopping before any change" >&2; exit 1; }
[ -s "$backup.part" ] || { rm -f "$backup.part"; echo "Backup is empty; stopping before any change" >&2; exit 1; }
mv "$backup.part" "$backup"
echo "    $(du -h "$backup" | cut -f1)"

echo "==> Applying migrations"
(cd backend && DATABASE_URL="$PROD_DATABASE_URL" uv run alembic upgrade head)

if [ "${SKIP_DATA:-0}" != 1 ]; then
  echo "==> Loading trade data (one transaction; the old data stays until it commits)"
  DATABASE_URL="$LIBPQ_URL" uv run ws-pipeline load

  echo "==> Embedding products for HS-code search (only new or changed ones)"
  (cd backend && DATABASE_URL="$PROD_DATABASE_URL" uv run python -m whitespace_api.jobs.embed_products)
fi

echo "==> Database size (free plan limit 512 MB)"
pg sh -c 'psql "$LIBPQ_URL" -Atc "select pg_size_pretty(pg_database_size(current_database()))"'
echo "Done. Backup: $backup"
