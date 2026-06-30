#!/bin/bash
# flash_oneplus.sh - 一加 Turbo6 移植 OnePlus 15 (Termux版)
set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL_PATH="$CURRENT_DIR/tools/fastboot"
IMG_DIR="$CURRENT_DIR/images"

if [ ! -f "$TOOL_PATH" ]; then
    echo "[ERROR] 未找到 fastboot 二进制文件，请放到 tools/fastboot"
    exit 1
fi

echo "=========================================================="
echo "          一加Turbo6 移植 OnePlus 15"
echo "              作者：酷安 空白没有输"
echo "=========================================================="
echo "警告：刷机前请备份数据，风险自负！"
echo "默认去除引导配置，切记不要低于Coloros16"
echo "警告：在继续之前，请确保已备份所有重要数据。风险自负。"
echo
echo "操作步骤："
echo "1. 请在手机设置中，启用“USB调试”模式。"
echo "2. 如果脚本卡在 < waiting for any device >，请检查 OTG 连接。"
echo "3. 手动将目标手机重启至 Fastboot 模式。"
echo "4. 使用USB数据线将目标手机连接到本机。"
echo
echo "请确认以上步骤已完成，然后按 Enter 开始刷机..."
read -r

echo "[检测设备]"
"$TOOL_PATH" devices
sleep 2

SKIP_LIST="modem vbmeta vbmeta_system vbmeta_vendor super"

# [1/6]
echo "[1/6] 刷入基带 modem A+B 槽位"
if [ -f "$IMG_DIR/modem.img" ]; then
    "$TOOL_PATH" flash modem_a "$IMG_DIR/modem.img"
    "$TOOL_PATH" flash modem_b "$IMG_DIR/modem.img"
fi

echo " 刷入 recovery 分区..."
if [ -f "$IMG_DIR/recovery.img" ]; then
    "$TOOL_PATH" flash recovery "$IMG_DIR/recovery.img"
fi

# [2/6]
echo "[2/6] 禁用AVB 刷入 vbmeta 系列 A+B 槽位"
if [ -f "$IMG_DIR/vbmeta.img" ]; then
    "$TOOL_PATH" --disable-verity --disable-verification flash vbmeta_a "$IMG_DIR/vbmeta.img"
    "$TOOL_PATH" --disable-verity --disable-verification flash vbmeta_b "$IMG_DIR/vbmeta.img"
fi
if [ -f "$IMG_DIR/vbmeta_system.img" ]; then
    "$TOOL_PATH" --disable-verity --disable-verification flash vbmeta_system_a "$IMG_DIR/vbmeta_system.img"
    "$TOOL_PATH" --disable-verity --disable-verification flash vbmeta_system_b "$IMG_DIR/vbmeta_system.img"
fi
if [ -f "$IMG_DIR/vbmeta_vendor.img" ]; then
    "$TOOL_PATH" --disable-verity --disable-verification flash vbmeta_vendor_a "$IMG_DIR/vbmeta_vendor.img"
    "$TOOL_PATH" --disable-verity --disable-verification flash vbmeta_vendor_b "$IMG_DIR/vbmeta_vendor.img"
fi

# [3/6]
echo "[3/6] 重启进入 Fastbootd 模式..."
"$TOOL_PATH" reboot fastboot
sleep 6

# [4/6]
echo "[4/6] 清理 COW 临时分区..."
PARTITIONS="system system_dlkm system_ext vendor product odm my_bigball my_carrier my_engineering my_heytap my_manifest my_product my_region my_stock odm_dlkm vendor_dlkm"
for p in $PARTITIONS; do
    "$TOOL_PATH" delete-logical-partition "${p}_a-cow" 2>/dev/null
    "$TOOL_PATH" delete-logical-partition "${p}_b-cow" 2>/dev/null
done
echo "COW 分区清理完成"

# [5/6]
echo "[5/6] 刷入所有镜像 A+B 双槽位..."
for img in "$IMG_DIR"/*.img; do
    name=$(basename "$img" .img)
    skip=0
    for s in $SKIP_LIST; do
        if [ "$name" = "$s" ]; then
            skip=1
            break
        fi
    done
    if [ "$skip" -eq 0 ]; then
        echo "正在刷入：${name}_a 和 ${name}_b"
        "$TOOL_PATH" flash "${name}_a" "$img"
        "$TOOL_PATH" flash "${name}_b" "$img"
    fi
done

# [6/6]
echo "[6/6] 刷入 super 分区..."
if [ -f "$IMG_DIR/super.img" ]; then
    "$TOOL_PATH" flash super "$IMG_DIR/super.img"
fi

echo "[清理] 清除 FRP 锁..."
"$TOOL_PATH" erase frp

echo "[设置] 强制切换并固定 A 槽..."
"$TOOL_PATH" set_active a

echo "=========================================================="
echo "              刷机全部完成！"
echo "            按 Enter 重启手机"
echo "=========================================================="
read -r
"$TOOL_PATH" reboot