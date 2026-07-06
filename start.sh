#!/bin/bash
# Skytree Flasher - 启动脚本 (HTTP)
cd "$(dirname "$0")"
source venv/bin/activate

export PUBLIC_DIR="$PWD/public"
export ROM_DIR="$PWD/public/rom"
export IMAGE_DIR="$PWD/public/image"

exec python app.py --port 12345 --lan "$@"
