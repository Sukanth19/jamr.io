#!/usr/bin/env bash
# Pull the latest code from GitHub, update dependencies, migrate and restart.
# Run on the server:
#   sudo bash /opt/jamr/deploy/update.sh
set -euo pipefail
cd /opt/jamr

sudo -u jamr git pull --ff-only
sudo -u jamr bash -c 'set -a; . /etc/jamr.env; set +a; bash deploy/build.sh'
# Pick up any changes to the service file
install -m 0644 deploy/jamr.service /etc/systemd/system/
systemctl daemon-reload
systemctl restart jamr
echo "Updated to $(sudo -u jamr git log -1 --format='%h %s')"
