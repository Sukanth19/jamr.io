#!/usr/bin/env bash
# Run one of jamr.io's Python scripts on the server with its settings loaded:
#   sudo bash /opt/jamr/deploy/run.sh create_overseer.py --list
#   sudo bash /opt/jamr/deploy/run.sh create_overseer.py <display-name>
set -euo pipefail
[ $# -ge 1 ] || { echo "Usage: sudo bash $0 <script.py> [args...]" >&2; exit 1; }
cd /opt/jamr
exec sudo -u jamr bash -c 'set -a; . /etc/jamr.env; set +a; exec venv/bin/python "$@"' _ "$@"
