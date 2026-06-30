#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# flash_tool/config.py
"""配置模块 - 版本、路径、常量"""

import os
import shutil
import logging

# ============ 版本信息 ============
TOOL_VERSION = "3.4.1"
# 更新日志：
# 3.4.1 (2026-07-01)
#   - 新增：脚本上传功能（WebDAV→OpenList + Hydra 预解析 + 安全扫描）
#   - 新增：底部悬浮「📤」上传按钮
#   - 前端：底部导航栏精简为 4 项
#   - 优化：去掉 flask-cors 依赖，使用原生 CORS headers
# 3.4.0 (2026-07-01)
#   - Hydra 引擎：修复 SH 嵌套 for 循环 + if 条件后的命令被 AST 解析器忽略的问题
#   - Hydra 引擎：新增 $(cd ... && pwd) 子 shell 简化，修复 CURRENT_DIR 推导
#   - Hydra 引擎：新增 set /p 用户输入模拟，set /a 算术表达式标记
#   - Hydra 引擎：新增 call :label 位置参数 %1 %2 传递支持
#   - Hydra 引擎：新增预设 BAT 系统变量（%CD%/%DATE%/%TIME%等）
#   - Hydra 引擎：新增 for /F 静态列表提取支持
#   - Hydra 引擎：新增 && / || 链式命令拆分提取
#   - Hydra 引擎：新增 note 字段（devices/getvar/reboot 步骤说明）
#   - Hydra 引擎：修复 SH 未定义变量展开为空字符串
#   - Hydra 引擎：修复 SH 引用赋值中引号嵌套导致路径错误
#   - Hydra 引擎：修复 BAT if exist 文件不存在时返回 None 而非 False
#   - Hydra 引擎：修复通配符 for 缺镜像时分区名非法
#   - Hydra 引擎：修复 prefixParams 未正确映射到 params
#   - ROM 解析：SH 脚本与 BAT 脚本一视同仁，is_native_sh 根据 is_simple 动态决定
#   - ROM 解析：script_type 根据解析结果动态设置，不再硬编码为 'sh'
#   - 原生执行：force_rewrite_fastboot_paths 跳过赋值语句避免路径拼接错误
#   - 原生执行：inject_reconnect_wait 替换原始 TOOL_PATH 赋值，确保 on 存在检查通过
#   - 原生执行：inject_reconnect_wait 变量覆盖移到脚本末尾避免被原始赋值覆盖
#   - 原生执行：reboot_re 正则扩展匹配 $VAR/"$VAR" 形式的变量调用
# 注意：当前使用 HTTP，若服务器支持 HTTPS 建议切换以保证下载完整性
UPDATE_REMOTE_BASE = "http://81.68.84.205:5244/sd/flash_tool"
UPDATE_ZIP_URL = f"{UPDATE_REMOTE_BASE}/flash_tool.zip"
UPDATE_CHECK_URL = f"{UPDATE_REMOTE_BASE}/config.py"

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
    return logging.getLogger('flash_tool')

logger = setup_logging()

# ============ WebDAV / OpenList 上传配置 ============
WEBDAV_URL = "http://81.68.84.205:5244/dav"
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