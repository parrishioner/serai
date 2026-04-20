#!/bin/bash
# Serai — Role Scan
# Called by launchd or crontab. Activates venv and runs eval.
# Update SERAI_DIR to match where you cloned the repo.
 
SERAI_DIR="/path/to/serai"
 
cd "$SERAI_DIR" || exit 1
source .venv/bin/activate
python eval_llm_scoring.py
