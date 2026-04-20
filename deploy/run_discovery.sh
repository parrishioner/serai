#!/bin/bash
# Serai — Company Discovery
# Called by launchd or crontab. Activates venv and runs discovery.
# Update SERAI_DIR to match where you cloned the repo.
 
SERAI_DIR="/path/to/serai"
 
cd "$SERAI_DIR" || exit 1
source .venv/bin/activate
python run_company_discovery.py
