#!/bin/bash
# ============================================================
# Google Pixel 工厂镜像刷写脚本 — flash-all.sh（典型版）
# 典型特征：函数定义、for 循环、条件判断、动态生成命令
# ============================================================

set -e

FASTBOOT=${FASTBOOT:-fastboot}
DEVICE=$(getprop ro.product.device 2>/dev/null || echo "unknown")

echo "==============================="
echo "刷机工具 - 设备: $DEVICE"
echo "==============================="

# 等待设备进入 fastboot
wait_for_device() {
    local timeout=$1
    local waited=0
    while [ $waited -lt $timeout ]; do
        if ${FASTBOOT} devices 2>/dev/null | grep -q "fastboot"; then
            echo "设备已连接"
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    echo "等待设备超时"
    return 1
}

# 刷写分区
flash_partition() {
    local part=$1
    local img=$2
    echo "刷写 $part <- $img"
    ${FASTBOOT} flash "$part" "images/$img"
}

echo "等待 fastboot 设备..."
wait_for_device 30

# 刷写 bootloader
${FASTBOOT} flash bootloader bootloader.img
${FASTBOOT} reboot-bootloader
wait_for_device 30

# 刷写 radio（如果存在）
if [ -f radio.img ]; then
    ${FASTBOOT} flash radio radio.img
    ${FASTBOOT} reboot-bootloader
    wait_for_device 15
fi

# 统一刷写系统镜像
for img in boot.img dtbo.img vendor_boot.img vendor.img system.img; do
    part=$(echo "$img" | sed 's/\.img$//')
    if [ -f "images/$img" ]; then
        flash_partition "$part" "$img"
    else
        echo "跳过 $img（文件不存在）"
    fi
done

# 清除用户数据
${FASTBOOT} -w

# 重启
${FASTBOOT} reboot

echo "刷机完成！"