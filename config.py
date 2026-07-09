#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Skytree Flasher / config.py
"""天树刷机 - 配置模块 - 版本、路径、常量"""

import os
import shutil
import logging

# ============ 版本信息 ============
TOOL_VERSION = "3.9.0"
UPDATE_REMOTE_BASE = "http://81.68.84.205:5244/sd/123456"
UPDATE_ZIP_URL = f"{UPDATE_REMOTE_BASE}/flash_tool.zip"
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/1248331222/flash-tool/master/config.py"

# ============ 运行时默认配置 ============
# 以下默认值可通过环境变量覆盖，保持无环境变量时行为不变
DEFAULT_SERVER_HOST = os.environ.get('SKYTREE_SERVER_HOST', '127.0.0.1')
DEFAULT_SERVER_PORT = int(os.environ.get('SKYTREE_SERVER_PORT', 8080))

SOCKETIO_PING_TIMEOUT = int(os.environ.get('SKYTREE_SOCKETIO_PING_TIMEOUT', 60))
SOCKETIO_PING_INTERVAL = int(os.environ.get('SKYTREE_SOCKETIO_PING_INTERVAL', 25))

# WebDAV 服务端点
WEBDAV_BASE_URL = os.environ.get('SKYTREE_WEBDAV_BASE_URL', 'http://81.68.84.205:5244/dav')
WEBDAV_PUBLIC_BASE_URL = os.environ.get('SKYTREE_WEBDAV_PUBLIC_BASE_URL', 'http://81.68.84.205:5244/sd/BD')

# 上传/OpenList 相关超时与限制
UPLOAD_WEBDAV_TIMEOUT_SHORT = int(os.environ.get('SKYTREE_UPLOAD_WEBDAV_TIMEOUT_SHORT', 10))
UPLOAD_WEBDAV_TIMEOUT_LONG = int(os.environ.get('SKYTREE_UPLOAD_WEBDAV_TIMEOUT_LONG', 30))
WEBDAV_PROXY_TIMEOUT = int(os.environ.get('SKYTREE_WEBDAV_PROXY_TIMEOUT', 30))
UPLOAD_PREVIEW_MAX_CHARS = int(os.environ.get('SKYTREE_UPLOAD_PREVIEW_MAX_CHARS', 100 * 1024))

# 更新检查/下载超时
UPDATE_CHECK_TIMEOUT = int(os.environ.get('SKYTREE_UPDATE_CHECK_TIMEOUT', 10))
UPDATE_DOWNLOAD_TIMEOUT = int(os.environ.get('SKYTREE_UPDATE_DOWNLOAD_TIMEOUT', 120))

# 批处理/线刷相关超时
BATCH_REBOOT_MAX_WAIT = int(os.environ.get('SKYTREE_BATCH_REBOOT_MAX_WAIT', 300))
FASTBOOT_FLASH_TIMEOUT = int(os.environ.get('SKYTREE_FASTBOOT_FLASH_TIMEOUT', 1800))
FASTBOOT_GETVAR_TIMEOUT = int(os.environ.get('SKYTREE_FASTBOOT_GETVAR_TIMEOUT', 5))

# ADB / 提取 / 步骤引擎 / 批处理辅助超时
ADB_DEVICES_TIMEOUT = int(os.environ.get('SKYTREE_ADB_DEVICES_TIMEOUT', 20))
EXTRACT_PROC_TIMEOUT = int(os.environ.get('SKYTREE_EXTRACT_PROC_TIMEOUT', 300))
STEP_ENGINE_GETVAR_TIMEOUT = int(os.environ.get('SKYTREE_STEP_ENGINE_GETVAR_TIMEOUT', 10))
BATCH_PROC_WAIT_TIMEOUT = int(os.environ.get('SKYTREE_BATCH_PROC_WAIT_TIMEOUT', 5))
BATCH_HELPERS_MAX_WAIT = int(os.environ.get('SKYTREE_BATCH_HELPERS_MAX_WAIT', 180))

# ============ 路径配置 ============
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BUNDLED_FASTBOOT_PATH = os.path.join(PROJECT_DIR, "bin", "fastboot-aarch64")

PUBLIC_DIR = os.environ.get(
    'PUBLIC_DIR',
    '/data/data/com.termux/files/home/storage/shared/123456'
)
PUBLIC_IMAGE_DIR = os.path.join(PUBLIC_DIR, "image")

ROM_DIR = os.environ.get('ROM_DIR', os.path.join(PUBLIC_DIR, 'rom'))
IMAGE_DIR = os.environ.get('IMAGE_DIR', os.path.join(PROJECT_DIR, 'image'))
STATIC_DIR = os.path.join(PROJECT_DIR, 'static')
FLASH_HISTORY_FILE = os.path.join(PUBLIC_DIR, "flash_history.json")
TASK_STATE_FILE = os.path.join(PROJECT_DIR, "tasks.json")

# ============ fastboot 检测 ============
def _detect_fastboot():
    """自动检测可用的 fastboot 路径"""
    # 1. 内置 bin
    if os.path.exists(BUNDLED_FASTBOOT_PATH):
        return BUNDLED_FASTBOOT_PATH
    # 2. 免root二进制
    no_root_fb = os.path.expanduser('~/.termux-adb/fastboot')
    if os.path.isfile(no_root_fb) and os.path.getsize(no_root_fb) > 1000:
        return no_root_fb
    # 3. 系统 fastboot
    system_fb = shutil.which('fastboot')
    if system_fb:
        return system_fb
    # 4. 回退
    return no_root_fb

DEFAULT_FASTBOOT_PATH = _detect_fastboot()
FASTBOOT_PATH = os.environ.get('FASTBOOT_PATH', DEFAULT_FASTBOOT_PATH)
ADB_PATH = os.environ.get("ADB_PATH", shutil.which("adb") or "")
TERMUX_USB_CMD = "termux-usb"

# ============ 支持的文件格式 ============
SUPPORTED_ROM_SUFFIXES = (
    '.zip', '.tar', '.tar.gz', '.tgz',
    '.tar.bz2', '.tbz2', '.tar.md5', '.7z', '.rar'
)

# ============ 高危分区黑名单 ============
DANGEROUS_PARTITIONS = {
    "bootloader", "aboot", "xbl", "xbl_a", "xbl_b",
    "modem", "modem_a", "modem_b",
    "persist", "persist_a", "persist_b",
    "ddr", "tz", "hyp", "keymaster", "rpm", "sbl1"
}

# ============ 合法分区名白名单 ============
VALID_PARTITIONS = {
    "boot", "boot_a", "boot_b",
    "recovery", "recovery_a", "recovery_b",
    "system", "system_a", "system_b",
    "vendor", "vendor_a", "vendor_b",
    "userdata", "cache",
    "dtbo", "dtbo_a", "dtbo_b",
    "vbmeta", "vbmeta_a", "vbmeta_b",
    "vbmeta_system", "vbmeta_system_a", "vbmeta_system_b",
    "super", "modem", "modem_a", "modem_b",
    "bluetooth", "dsp", "frp", "keystore", "metadata",
    "misc", "oem", "persist", "persist_a", "persist_b",
    "qupfw", "storsec", "uefisecapp", "xbl", "xbl_a", "xbl_b",
    "xbl_config", "xbl_config_a", "xbl_config_b",
}

# ============ Flask 配置 ============
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
MAX_CONTENT_LENGTH = 16 * 1024 * 1024

# ============ 日志配置 ============
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
LOG_FILE = os.environ.get('LOG_FILE', os.path.join(PROJECT_DIR, 'flash_tool.log'))

def setup_logging():
    """配置日志系统"""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('skytree_flasher')

logger = setup_logging()

# ============ WebDAV / OpenList 上传配置 ============
# 注意：此账号（123456/123456）仅用于用户上传刷机脚本到 OpenList。
# 项目打包上传到 /TY/flash_tool/ 请使用超级账号（见记忆或环境变量 WEBDAV_ADMIN_USER/WEBDAV_ADMIN_PASS）。
# 旧入口兼容：WEBDAV_URL 指向与 WEBDAV_BASE_URL 相同的地址
WEBDAV_URL = WEBDAV_BASE_URL
WEBDAV_USER = "123456"
WEBDAV_PASS = "123456"
UPLOAD_DIR = os.path.join(PUBLIC_DIR, "uploaded_scripts")

# ============ 超时与轮询配置 ============
FASTBOOT_DEFAULT_TIMEOUT = 1800
ADB_DEFAULT_TIMEOUT = 300
BL_QUERY_TIMEOUT = 15
DEVICE_INFO_TIMEOUT = 10
USB_CHECK_TIMEOUT = 10
USB_GRANT_TIMEOUT = 10
REBOOT_TIMEOUT = 8
WAIT_FASTBOOT_INITIAL = 1
TASK_LOG_LIMIT = 300
BATTERY_LOW_THRESHOLD = 20

# ============ 初始化目录 ============
def init_directories():
    """自动创建必要目录"""
    for d in [ROM_DIR, IMAGE_DIR, STATIC_DIR, PUBLIC_DIR, PUBLIC_IMAGE_DIR]:
        os.makedirs(d, exist_ok=True)
        logger.debug(f"目录已就绪: {d}")