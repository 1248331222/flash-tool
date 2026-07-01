#!/bin/bash
# ============================================================
# 复杂刷机脚本 - Shell 版本，功能与 Windows 版对应
# 用法：./complex_flash.sh [选项]
#   选项参见 -h
# ============================================================

set -euo pipefail

# ---------- 全局配置 ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/flash_$(date +%Y%m%d_%H%M%S).log"

FASTBOOT_DEFAULT="fastboot"   # 假设已在 PATH 中
IMG_DIR_DEFAULT="${SCRIPT_DIR}/image"
DEVICE_DEFAULT="ACE竞速版C13c05"
MAKER_DEFAULT="酷安@无为真大道"
PARTITION_LIST_DEFAULT="preloader_raw lk apusys audio_dsp boot ccu cdt_engineering dpm dtbo gpueb gz mcf_ota mcupm md1img mvpu_algo pi_img scp spmfw sspm tee vcp vendor_boot vbmeta vbmeta_system vbmeta_vendor"
PRINT_LOOP=3

# 运行时变量
FASTBOOT="$FASTBOOT_DEFAULT"
IMG_DIR="$IMG_DIR_DEFAULT"
DEVICE="$DEVICE_DEFAULT"
MAKER="$MAKER_DEFAULT"
PARTITION_LIST="$PARTITION_LIST_DEFAULT"
WIPE_DATA=false
NO_REBOOT=false
SKIP_CHECK=false
AUTO_FLASH=false
STATE="ready"

# ---------- 函数定义 ----------
log() {
    local msg="[$(date '+%H:%M:%S')] $*"
    echo "$msg" | tee -a "$LOG_FILE"
}

log_only() {
    echo "[$(date '+%H:%M:%S')] $*" >> "$LOG_FILE"
}

usage() {
    cat << EOF
用法: $0 [选项]
  -f, --fastboot PATH    指定 fastboot 可执行文件路径
  -i, --img DIR          指定镜像文件目录
  -p, --partition "LIST" 指定要刷写的分区（空格分隔），默认全部
  -w, --wipe             刷机后清除用户数据
  -n, --no-reboot        刷机完成后不自动重启
  -s, --skip-check       跳过设备检测
  -a, --auto             自动执行全部刷写（不进入菜单）
  -h, --help             显示此帮助
示例:
  $0 -i ./images -p "boot recovery" -w
EOF
    exit 0
}

check_device() {
    log "检测设备连接..."
    if ! fastboot devices | grep -q "fastboot"; then
        log "错误: 未检测到 Fastboot 设备。请确保手机已进入 Bootloader 模式。"
        exit 1
    fi
    log "设备已连接。"
}

flash_partition() {
    local part="$1"
    local img_path="${IMG_DIR}/${part}.img"
    if [[ ! -f "$img_path" ]]; then
        log "警告: 镜像 ${img_path} 不存在，跳过。"
        return 0
    fi
    log "刷写 ${part}_a ..."
    if ! "$FASTBOOT" flash "${part}_a" "$img_path" >> "$LOG_FILE" 2>&1; then
        log "错误: 刷写 ${part}_a 失败！"
        exit 1
    fi
    log "刷写 ${part}_b ..."
    if ! "$FASTBOOT" flash "${part}_b" "$img_path" >> "$LOG_FILE" 2>&1; then
        log "错误: 刷写 ${part}_b 失败！"
        exit 1
    fi
    log "分区 ${part} 刷写完成。"
}

do_erase_meta() {
    log "擦除 metadata 分区..."
    if ! "$FASTBOOT" erase metadata >> "$LOG_FILE" 2>&1; then
        log "警告: 擦除 metadata 失败（可能不存在）。"
    else
        log "metadata 已擦除。"
    fi
}

do_wipe() {
    log "开始清除用户数据 (fastboot -w)..."
    if ! "$FASTBOOT" -w >> "$LOG_FILE" 2>&1; then
        log "警告: fastboot -w 失败，尝试单独擦除 userdata 和 cache..."
        "$FASTBOOT" erase userdata >> "$LOG_FILE" 2>&1 || true
        "$FASTBOOT" erase cache >> "$LOG_FILE" 2>&1 || true
    fi
    log "数据清除操作完成。"
}

do_reboot() {
    log "重启设备..."
    if ! "$FASTBOOT" reboot >> "$LOG_FILE" 2>&1; then
        log "错误: 重启失败，请手动重启。"
    else
        log "设备已重启。"
    fi
}

# ---------- 命令行参数解析 ----------
TEMP=$(getopt -o f:i:p:wnsah --long fastboot:,img:,partition:,wipe,no-reboot,skip-check,auto,help -n "$0" -- "$@")
eval set -- "$TEMP"
while true; do
    case "$1" in
        -f|--fastboot) FASTBOOT="$2"; shift 2 ;;
        -i|--img) IMG_DIR="$2"; shift 2 ;;
        -p|--partition) PARTITION_LIST="$2"; shift 2 ;;
        -w|--wipe) WIPE_DATA=true; shift ;;
        -n|--no-reboot) NO_REBOOT=true; shift ;;
        -s|--skip-check) SKIP_CHECK=true; shift ;;
        -a|--auto) AUTO_FLASH=true; shift ;;
        -h|--help) usage ;;
        --) shift; break ;;
        *) echo "内部错误！"; exit 1 ;;
    esac
done

# ---------- 初始化 ----------
log "========== 刷机开始 [$(date)] =========="
log "设备: $DEVICE"
log "制作: $MAKER"
log "Fastboot路径: $FASTBOOT"
log "镜像目录: $IMG_DIR"

# 检查 fastboot 可执行性
if ! command -v "$FASTBOOT" &> /dev/null && [[ ! -x "$FASTBOOT" ]]; then
    log "错误: 找不到 fastboot 可执行文件 - $FASTBOOT"
    exit 1
fi

# 检查镜像目录
if [[ ! -d "$IMG_DIR" ]]; then
    log "警告: 镜像目录不存在 - $IMG_DIR"
    if $AUTO_FLASH; then
        log "自动模式终止，目录不存在。"
        exit 1
    fi
fi

# 设备检测
if ! $SKIP_CHECK; then
    check_device
else
    log "已跳过设备检测。"
fi

# ---------- 交互菜单或自动模式 ----------
if $AUTO_FLASH; then
    log "自动模式启动，将执行全部刷写操作。"
    goto_auto_flash
else
    while true; do
        clear
        echo "========== 刷机主菜单 =========="
        echo "  1. 刷写所有分区（默认列表）"
        echo "  2. 刷写指定分区"
        echo "  3. 擦除 metadata 并设置活动分区"
        echo "  4. 清除用户数据 (wipe)"
        echo "  5. 重启设备"
        echo "  6. 查看日志"
        echo "  7. 退出"
        echo "================================"
        read -p "请选择 [1-7]: " choice
        case $choice in
            1) goto_auto_flash; break ;;
            2)
                read -p "请输入要刷写的分区（空格分隔，直接回车使用全部）: " custom_part
                if [[ -n "$custom_part" ]]; then
                    PARTITION_LIST="$custom_part"
                fi
                goto_auto_flash; break
                ;;
            3) do_erase_meta; do_set_active ;;
            4) do_wipe ;;
            5) do_reboot ;;
            6)
                if [[ -f "$LOG_FILE" ]]; then
                    less "$LOG_FILE"
                else
                    echo "日志文件不存在。"
                fi
                ;;
            7) log "用户退出。"; exit 0 ;;
            *) echo "无效选择，请重新输入。" ;;
        esac
    done
fi

# ---------- 核心刷写流程（函数） ----------
goto_auto_flash() {
    log "进入刷写流程..."
    log "即将刷写分区: $PARTITION_LIST"

    # 前置提醒循环
    log "----------------刷机前置提醒循环----------------"
    for ((i=1; i<=PRINT_LOOP; i++)); do
        log "第${i}遍提醒：刷机期间不要点击鼠标"
        if [[ "$STATE" == "ready" ]]; then
            log "检测状态正常，即将进入刷机流程"
        fi
    done
    log "------------------------------------------------"

    # 确保 bootloader
    log "执行: $FASTBOOT reboot bootloader"
    "$FASTBOOT" reboot bootloader >> "$LOG_FILE" 2>&1 || log "警告: reboot bootloader 失败，可能已处于 fastboot 模式。"

    # 擦除 metadata
    do_erase_meta

    # 刷写 super 分区
    if [[ -f "${IMG_DIR}/super.img" ]]; then
        log "刷写 super 分区..."
        if "$FASTBOOT" flash super "${IMG_DIR}/super.img" -S 64M >> "$LOG_FILE" 2>&1; then
            log "super 刷写成功。"
        else
            log "错误: 刷写 super 失败！"
            exit 1
        fi
    else
        log "未找到 super.img，跳过。"
    fi

    # 循环刷写分区列表
    log "开始刷写各个分区（A/B 双槽）..."
    for part in $PARTITION_LIST; do
        log "正在处理分区: $part"
        flash_partition "$part"
    done

    # 擦除 metadata 并设置活动分区
    do_erase_meta
    log "设置活动分区为 a"
    if "$FASTBOOT" set_active a >> "$LOG_FILE" 2>&1; then
        log "活动分区已设为 a。"
    else
        log "警告: set_active 失败。"
    fi

    # 清除数据（若指定）
    if $WIPE_DATA; then
        do_wipe
    fi

    # 刷机完成校验
    log "----------------刷机完成校验循环----------------"
    for ((j=1; j<=2; j++)); do
        log "流程校验提示 $j"
        if [[ -n "$DEVICE" ]]; then
            log "设备名称变量加载成功"
        fi
    done
    log "------------------------------------------------"

    log "刷写流程执行完毕。"

    if $NO_REBOOT; then
        log "根据参数 -no-reboot，不自动重启。请手动重启。"
    else
        do_reboot
    fi
}

# ---------- 额外功能：设置活动分区（菜单用） ----------
do_set_active() {
    log "设置活动分区为 a"
    "$FASTBOOT" set_active a >> "$LOG_FILE" 2>&1 && log "成功。" || log "失败。"
}

# 结束
log "========== 刷机结束 [$(date)] =========="
echo "日志已保存至: $LOG_FILE"
exit 0