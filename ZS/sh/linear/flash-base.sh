#!/bin/bash
# ============================================================
# 基础刷写脚本 — flash-base.sh（Google Pixel 风格）
# 典型特征：顺序执行 fastboot 命令
# ============================================================

FASTBOOT=${FASTBOOT:-fastboot}
WORK_DIR=$(dirname "$0")

cd "$WORK_DIR"

echo "刷写基础分区..."

${FASTBOOT} flash bootloader_a bootloader.img
${FASTBOOT} flash bootloader_b bootloader.img

${FASTBOOT} reboot-bootloader
sleep 3

${FASTBOOT} flash radio_a radio.img
${FASTBOOT} flash radio_b radio.img

${FASTBOOT} reboot-bootloader
sleep 3

echo "基础分区刷写完成"