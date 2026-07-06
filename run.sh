#!/data/data/com.termux/files/usr/bin/bash
# Skytree Flasher / run.sh
cd "$(dirname "$0")"
exec python app.py "$@"