#!/data/data/com.termux/files/usr/bin/bash
# flash_tool/run.sh
cd "$(dirname "$0")"
exec python app.py "$@"
