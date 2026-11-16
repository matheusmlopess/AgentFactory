#!/usr/bin/env bash
# Back up the API's /data volume (SQLite database + registry ZIPs) to ./backups/agentfactory-<UTC>.tar.gz.
# SQLite is copied with its online backup API, so the API can keep running.
# Cron example (daily 03:15): 15 3 * * * cd /opt/agentfactory/deploy/vps && ./backup.sh >> backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p backups
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
docker compose exec -T api python -c "
import sqlite3
src = sqlite3.connect('/data/agentfactory.db'); dst = sqlite3.connect('/data/backup.db')
src.backup(dst); dst.close(); src.close()"
docker compose exec -T api sh -c "mkdir -p /data/registry && tar -C /data -czf - backup.db registry" \
  > "backups/agentfactory-${STAMP}.tar.gz"
docker compose exec -T api rm -f /data/backup.db
ls -1t backups/agentfactory-*.tar.gz | tail -n +15 | xargs -r rm --   # keep the newest 14
echo "backup: backups/agentfactory-${STAMP}.tar.gz"
