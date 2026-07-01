#!/bin/bash
# ============================================================
# 边界情况: adb + fastboot 混合 + 管道 + 子 shell
# 测试引擎对非标准调用的处理
# ============================================================

FASTBOOT=${FASTBOOT:-fastboot}
ADB=${ADB:-adb}

echo "等待设备..."

# adb 重启到 bootloader（非 fastboot 命令）
$ADB reboot bootloader
sleep 5

# 管道检测
if $FASTBOOT devices 2>/dev/null | grep -q "fastboot"; then
    echo "设备已连接"
else
    echo "设备未连接"
    exit 1
fi

# 子 shell 获取分区列表
partitions=$(ls images/*.img 2>/dev/null | xargs -n1 basename | sed 's/\.img$//')

# 动态变量
SLOT=$(getprop ro.boot.slot 2>/dev/null || echo "_a")

# 非标准路径 fastboot
TOOL_PATH=$(dirname "$0")/tools
${TOOL_PATH}/fastboot flash bootloader bootloader.img

# 变量内联赋值
PARTITION=boot && $FASTBOOT flash $PARTITION images/${PARTITION}.img

# for 循环 + 字符串操作
for img in images/*.img; do
    name=$(basename "$img" .img)
    $FASTBOOT flash "$name" "$img"
done

# 算术运算
COUNT=0
while [ $COUNT -lt 3 ]; do
    $FASTBOOT getvar product 2>/dev/null
    COUNT=$((COUNT + 1))
done

$FASTBOOT reboot

echo "完成"