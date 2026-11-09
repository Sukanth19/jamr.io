#!/usr/bin/env bash
# Daily database backup (installed to /etc/cron.daily). Keeps the last 7.
set -euo pipefail
DIR=/opt/jamr/backups
mkdir -p "$DIR"
sudo -u postgres pg_dump jamr_io | gzip > "$DIR/jamr-$(date +%F).sql.gz"
ls -1t "$DIR"/jamr-*.sql.gz | tail -n +8 | xargs -r rm --
chmod 600 "$DIR"/jamr-*.sql.gz
