#!/usr/bin/env bash
# Install Python dependencies and run database migrations. Runs as the app
# user with /etc/jamr.env loaded (setup.sh and update.sh call it).
set -euo pipefail
cd /opt/jamr

[ -x venv/bin/python ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt

venv/bin/alembic upgrade head
