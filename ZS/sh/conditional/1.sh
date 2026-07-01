#!/bin/bash
# 移植线刷工具 - OnePlus Turbo6 移植 OnePlus 15
# 作者：酷安 空白没有输

# 设置编码（中文支持）
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

# 获取脚本所在目录
CURRENT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL_PATH="${CURRENT_DIR}/tools/fastboot"
IMG_DIR="${CURRENT_DIR}/images"

# 检查 fastboot 是否存在
if [ ! -f "$TOOL_PATH" ] && ! command -v fastboot &>/dev/null; then
    clear
    echo
    echo "[ERROR] 未找到 fastboot 可执行文件（尝试路径：$TOOL_PATH 或系统 PATH）"
    read -p "按任意键退出..." -n1
    exit 1
fi

# 如果指定路径的工具存在则使用，否则使用系统 fastboot
if [ -f "$TOOL_PATH" ]; then
    FASTBOOT="$TOOL_PATH"
else
    FASTBOOT="fastboot"
fi

clear
echo "=========================================================="
echo "          一加Turbo6 移植 OnePlus 15 "
echo "              作者：酷安 空白没有输"
echo "=========================================================="
echo "警告：刷机前请备份数据，风险自负！"
echo "默认去除引导配置切记不要低于Coloros16"
echo "警告：在继续之前，请确保已备份所有重要数据。风险自负。"
echo
echo "操作步骤："
echo "1. 请在手机设置中，启用“USB调试”模式。"
echo "2. 如果脚本卡在 < waiting for any device >，请安装Fastboot驱动。"
echo "3. 手动将手机重启至 Fastboot 模式（关机状态下同时按住 音量下键 和 电源键）。"
echo "4. 使用USB数据线将手机连接到电脑。"
echo
echo "请确认以上步骤已完成，然后按任意键开始刷机..."
echo "=========================================================="
read -p "" -n1

echo
echo "[检测设备] 等待设备连接..."
"$FASTBOOT" devices
if [ $? -ne 0 ]; then
    echo "[错误] 未检测到设备，请检查驱动与连接"
    read -p "按任意键退出..." -n1
    exit 1
fi

# 跳过列表（这些分区单独处理）
SKIP_LIST="modem vbmeta vbmeta_system vbmeta_vendor super"

echo
echo "[1/6] 刷入基带 modem A+B 槽位"
if [ -f "${IMG_DIR}/modem.img" ]; then
    "$FASTBOOT" flash modem_a "${IMG_DIR}/modem.img"
    "$FASTBOOT" flash modem_b "${IMG_DIR}/modem.img"
fi

echo
echo " 刷入 recovery 分区..."
if [ -f "${IMG_DIR}/recovery.img" ]; then
    "$FASTBOOT" flash recovery "${IMG_DIR}/recovery.img"
fi

echo
echo "[2/6] 禁用AVB 刷入 vbmeta 系列 A+B 槽位"
if [ -f "${IMG_DIR}/vbmeta.img" ]; then
    "$FASTBOOT" --disable-verity --disable-verification flash vbmeta_a "${IMG_DIR}/vbmeta.img"
    "$FASTBOOT" --disable-verity --disable-verification flash vbmeta_b "${IMG_DIR}/vbmeta.img"
fi
if [ -f "${IMG_DIR}/vbmeta_system.img" ]; then
    "$FASTBOOT" --disable-verity --disable-verification flash vbmeta_system_a "${IMG_DIR}/vbmeta_system.img"
    "$FASTBOOT" --disable-verity --disable-verification flash vbmeta_system_b "${IMG_DIR}/vbmeta_system.img"
fi
if [ -f "${IMG_DIR}/vbmeta_vendor.img" ]; then
    "$FASTBOOT" --disable-verity --disable-verification flash vbmeta_vendor_a "${IMG_DIR}/vbmeta_vendor.img"
    "$FASTBOOT" --disable-verity --disable-verification flash vbmeta_vendor_b "${IMG_DIR}/vbmeta_vendor.img"
fi

echo
echo "[3/6] 重启进入 Fastbootd 模式..."
"$FASTBOOT" reboot fastboot
sleep 6

echo
echo "[4/6] 清理 COW 临时分区..."
PARTITIONS="system system_dlkm system_ext vendor product odm my_bigball my_carrier my_engineering my_heytap my_manifest my_product my_region my_stock odm_dlkm vendor_dlkm"
for part in $PARTITIONS; do
    "$FASTBOOT" delete-logical-partition "${part}_a-cow" >/dev/null 2>&1
    "$FASTBOOT" delete-logical-partition "${part}_b-cow" >/dev/null 2>&1
done
echo "COW 分区清理完成"

echo
echo "[5/6] 刷入所有镜像 A+B 双槽位..."
for f in "${IMG_DIR}"/*.img; do
    # 提取文件名（不含路径和扩展名）
    name="$(basename "$f" .img)"
    # 检查是否在跳过列表中
    skip=0
    for s in $SKIP_LIST; do
        if [ "$name" = "$s" ]; then
            skip=1
            break
        fi
    done
    if [ $skip -eq 0 ]; then
        echo "正在刷入：${name}_a 和 ${name}_b"
        "$FASTBOOT" flash "${name}_a" "$f"
        "$FASTBOOT" flash "${name}_b" "$f"
    fi
done

echo
echo "[6/6] 刷入 super 分区..."
if [ -f "${IMG_DIR}/super.img" ]; then
    "$FASTBOOT" flash super "${IMG_DIR}/super.img"
fi

echo
echo "[清理] 清除 FRP 锁..."
"$FASTBOOT" erase frp

echo
echo "[设置] 强制切换并固定 A 槽..."
"$FASTBOOT" set_active a

echo
echo "=========================================================="
echo "              刷机全部完成！"
echo "            按任意键重启手机"
echo "=========================================================="
read -p "" -n1
"$FASTBOOT" reboot