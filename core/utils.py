# -*- coding: utf-8 -*-
# Skytree Flasher / core/utils.py
"""
core/utils.py — API 响应辅助、路径/文件名校验、错误诊断
从单文件版提取，函数逻辑保持不变。
"""

import os
import re
from urllib.parse import unquote

from flask import jsonify

from config import (
    ROM_DIR,
    IMAGE_DIR,
    PUBLIC_DIR,
    PUBLIC_IMAGE_DIR,
    DANGEROUS_PARTITIONS,
    SUPPORTED_ROM_SUFFIXES,
    logger,
)


# ============ API 响应辅助函数 ============
def api_ok(data=None, msg=""):
    """统一成功响应"""
    resp = {"success": True}
    if data is not None:
        resp["data"] = data
    if msg:
        resp["msg"] = msg
    return jsonify(resp)

def api_err(msg, status=200, **extra):
    """统一错误响应"""
    resp = {"success": False, "error": msg}
    resp.update(extra)
    return jsonify(resp), status


# ======================================================================
# 模块: utils/validator.py
# ======================================================================


def sanitize_path(base_dir: str, user_path: str) -> str:
    """
    安全地拼接路径，防止路径遍历攻击

    Args:
        base_dir: 基础目录（安全边界）
        user_path: 用户提供的路径

    Returns:
        安全的完整路径

    Raises:
        ValueError: 如果路径尝试逃逸基础目录
    """
    # 规范化路径，处理 .. 和多余斜杠
    base_dir = os.path.normpath(base_dir)
    decoded_path = user_path

    # 处理可能的 URL 编码
    if '%' in user_path:
        decoded_path = unquote(user_path)

    # 规范化用户路径
    decoded_path = os.path.normpath(decoded_path)

    # 拼接完整路径
    full_path = os.path.normpath(os.path.join(base_dir, decoded_path))

    # 解析符号链接，确保符号链接被正确解析（#13）
    base = os.path.realpath(base_dir)
    full = os.path.realpath(full_path)

    # 确保结果路径仍在基础目录内
    if not full.startswith(base + os.sep) and full != base:
        raise ValueError(f"非法路径: 尝试访问 {full}")

    return full


def validate_partition_name(name: str) -> str:
    """
    校验分区名，只允许字母、数字、下划线

    Args:
        name: 分区名

    Returns:
        规范化的分区名（小写）

    Raises:
        ValueError: 如果分区名非法
    """
    if not name:
        raise ValueError("分区名不能为空")

    # 只允许字母、数字、下划线
    if not re.match(r'^[a-zA-Z0-9_]+$', name):
        raise ValueError(f"非法分区名: {name}")

    return name.lower()


def is_dangerous_partition(partition: str) -> bool:
    """
    检查是否为高危分区

    Args:
        partition: 分区名

    Returns:
        是否为高危分区
    """
    return partition.lower() in DANGEROUS_PARTITIONS


def validate_image_filename(filename: str) -> str:
    """
    校验镜像文件名

    Args:
        filename: 文件名

    Returns:
        安全的文件名

    Raises:
        ValueError: 如果文件名非法
    """
    if not filename:
        raise ValueError("文件名不能为空")

    # 只允许 .img 文件
    if not filename.lower().endswith('.img'):
        raise ValueError("只支持 .img 镜像文件")

    # 检查危险字符
    dangerous_chars = ['..', '\\', '\x00']
    for char in dangerous_chars:
        if char in filename:
            raise ValueError(f"文件名包含非法字符: {filename}")

    return filename


def validate_image_rel_path(path: str) -> str:
    """
    校验刷机包内部镜像相对路径，允许 image/super.img 这类脚本路径。
    """
    if not path:
        raise ValueError("镜像路径不能为空")
    if '%' in path:
        path = unquote(path)
    normalized = os.path.normpath(path.replace("\\", "/")).lstrip("/")
    if (
        not normalized
        or normalized.startswith("../")
        or normalized == ".."
        or os.path.isabs(normalized)
        or "\x00" in path
    ):
        raise ValueError(f"非法镜像路径: {path}")
    if not normalized.lower().endswith(".img"):
        return normalized
    return normalized


# 常见镜像子目录前缀（按优先级排序）
_IMAGE_SUB_DIRS = ('images/', 'image/', 'firmware/', 'super/', '')


def _recursive_find_image(base_dir: str, basename: str) -> str | None:
    """在 base_dir 下递归查找名为 basename 的 .img 文件（限制深度避免过慢）。"""
    if not os.path.isdir(base_dir):
        return None
    basename_lower = basename.lower()
    for dirpath, dirnames, filenames in os.walk(base_dir):
        # 剪枝：跳过隐藏目录和无关大目录
        dirnames[:] = [d for d in dirnames if not d.startswith(".")
                       and d not in ("Android", "DCIM", "Pictures", "Movies", "Music")]
        for fn in filenames:
            if fn.lower() == basename_lower:
                return os.path.join(dirpath, fn)
    return None


def resolve_image_abs_path(image_name: str, rom_dir: str, rom_name: str = None) -> tuple:
    """
    统一镜像路径解析器（解析阶段 + 执行阶段共用）。

    按优先级依次尝试：
      1. rom_dir（脚本所在目录）+ image_name
      2. ROM_DIR/rom_folder + image_name
      3. 上述各目录 + 常见子目录前缀（images/、image/、firmware/、super/）
      4. 递归查找 rom_dir 和 ROM_DIR/rom_folder

    Args:
        image_name: 脚本中的镜像路径（相对/绝对/纯文件名）
        rom_dir: 脚本所在目录（os.path.dirname(script_path)）
        rom_name: ROM 包名（用于定位 ROM_DIR 下的解压目录）

    Returns:
        (abs_path, True)  找到时返回绝对路径
        (None, False)     未找到
    """
    if not image_name:
        return None, False

    # 标准化路径分隔符
    rel = image_name.strip().strip('"').replace("\\", "/").lstrip("/").lstrip("./")
    if not rel or "\x00" in rel or ".." in rel:
        return None, False

    basename = os.path.basename(rel)
    is_pure_name = "/" not in rel

    # 构建候选基础目录列表
    candidate_dirs = []
    if rom_dir and os.path.isdir(rom_dir):
        candidate_dirs.append(os.path.abspath(rom_dir))

    if rom_name:
        rom_folder = rom_name if os.path.isdir(os.path.join(ROM_DIR, rom_name)) else get_rom_base_name(rom_name)
        rom_root = os.path.join(ROM_DIR, rom_folder)
        if os.path.isdir(rom_root):
            rom_root = os.path.abspath(rom_root)
            if rom_root not in candidate_dirs:
                candidate_dirs.append(rom_root)

    # 阶段1：直接拼接 + 子目录前缀
    for base in candidate_dirs:
        # 直接拼接完整相对路径
        try:
            full = sanitize_path(base, rel)
            if os.path.exists(full):
                return full, True
        except (ValueError, FileNotFoundError):
            pass
        # 纯文件名时尝试常见子目录前缀
        if is_pure_name:
            for sub in _IMAGE_SUB_DIRS:
                if not sub:
                    continue
                try:
                    full = sanitize_path(base, sub + rel)
                    if os.path.exists(full):
                        return full, True
                except (ValueError, FileNotFoundError):
                    continue

    # 阶段2：递归查找（兜底）
    if basename.lower().endswith(".img"):
        for base in candidate_dirs:
            found = _recursive_find_image(base, basename)
            if found:
                return os.path.abspath(found), True

    return None, False


def get_allowed_image_roots() -> list:
    """
    WebUSB / 绝对路径模式允许查找镜像的根目录。
    与 routes/api_flash.py 中 _allowed_image_roots 保持一致，集中在此避免重复。
    """
    return [
        os.path.abspath(PUBLIC_DIR),
        os.path.abspath(ROM_DIR),
        os.path.abspath(IMAGE_DIR),
        "/sdcard",
        "/storage/emulated/0",
    ]


def is_path_under_allowed_roots(full: str) -> bool:
    """
    限制只能读取公共刷机目录/已解压目录/外置存储中的文件。
    """
    full = os.path.abspath(os.path.expanduser(full))
    return any(full == root or full.startswith(root + os.sep) for root in get_allowed_image_roots())


def validate_absolute_image_path(path: str) -> str:
    """
    校验绝对路径镜像。

    Args:
        path: 用户输入的绝对路径，如 /sdcard/123456/image/vbmeta.img

    Returns:
        规范化的绝对路径

    Raises:
        ValueError: 路径不合法、不在允许目录、不存在或不是 .img 文件
    """
    if not path:
        raise ValueError("镜像路径不能为空")
    if '%' in path:
        path = unquote(path)
    if '\x00' in path or '..' in path:
        raise ValueError(f"镜像路径包含非法字符: {path}")
    if not os.path.isabs(path):
        raise ValueError("请使用绝对路径，例如 /sdcard/123456/image/vbmeta.img")
    full = os.path.abspath(os.path.expanduser(path))
    if not is_path_under_allowed_roots(full):
        raise ValueError("镜像路径不在允许目录内，请放到 123456、已解压线刷包或 /sdcard 下")
    if not full.lower().endswith(".img"):
        return full
    if not os.path.exists(full):
        raise ValueError("镜像文件不存在")
    return full


def validate_rom_filename(filename: str) -> str:
    """
    校验 ROM 包文件名

    Args:
        filename: 文件名

    Returns:
        安全的文件名

    Raises:
        ValueError: 如果文件名非法
    """
    if not filename:
        raise ValueError("文件名不能为空")


    # 检查后缀
    name_lower = filename.lower()
    valid = False
    for suffix in SUPPORTED_ROM_SUFFIXES:
        if name_lower.endswith(suffix):
            valid = True
            break

    if not valid:
        raise ValueError(f"不支持的文件格式: {filename}")

    # 检查危险字符
    dangerous_chars = ['..', '\\', '\x00']
    for char in dangerous_chars:
        if char in filename:
            raise ValueError(f"文件名包含非法字符: {filename}")

    return filename


def validate_fastboot_args(args: list) -> list:
    """
    校验 fastboot 命令参数

    Args:
        args: 参数列表

    Returns:
        安全的参数列表

    Raises:
        ValueError: 如果参数包含危险字符
    """
    dangerous_patterns = [';', '|', '&', '$', '`', '\n', '\r', '..']

    for arg in args:
        for pattern in dangerous_patterns:
            if pattern in arg:
                raise ValueError(f"参数包含非法字符: {arg}")

    return args


def get_image_path(source: str, image_name: str, rom_name: str = None) -> str:
    """
    根据来源获取镜像完整路径

    Args:
        source: 来源类型 (local/rom/public/path)
        image_name: 镜像文件名或绝对路径（source=path 时为绝对路径）
        rom_name: ROM包名（source=rom 时需要）

    Returns:
        镜像完整路径

    Raises:
        ValueError: 如果路径不合法或文件不存在
    """
    # 【修复】：统一将 Windows 反斜杠转换为正斜杠，解决跨平台路径问题
    if isinstance(image_name, str):
        image_name = image_name.replace('\\', '/')
    # 【修复】：只对 .img 文件进行完整校验，非 .img 文件（如 crclist.txt）跳过
    is_img = image_name.lower().endswith('.img') if isinstance(image_name, str) else False
    if source == "rom":
        if not rom_name:
            raise ValueError("未指定刷机包")
        if is_img:
            image_name = validate_image_rel_path(image_name)
        rom_folder = rom_name if os.path.isdir(os.path.join(ROM_DIR, rom_name)) else get_rom_base_name(rom_name)
        base_dir = os.path.join(ROM_DIR, rom_folder)
        try:
            return sanitize_path(base_dir, image_name)
        except (ValueError, FileNotFoundError):
            if is_img:
                pass  # 往下走兜底逻辑
            else:
                raise
        # 【修复】：如果原始路径找不到，对纯文件名尝试补齐常见子目录前缀
        if is_img and '/' not in image_name and '\\' not in image_name:
            for sub_dir in _IMAGE_SUB_DIRS:
                if not sub_dir:
                    continue
                test_rel = sub_dir + image_name
                try:
                    path = sanitize_path(base_dir, test_rel)
                    if os.path.exists(path):
                        return path
                except (ValueError, FileNotFoundError):
                    continue
        # 【修复】：最后兜底——在 ROM 根目录下递归查找同名 .img
        if is_img:
            found = _recursive_find_image(base_dir, os.path.basename(image_name))
            if found:
                return found
        raise FileNotFoundError(f"镜像不存在：{image_name}")

    elif source == "public":
        validate_image_filename(image_name)
        return sanitize_path(PUBLIC_IMAGE_DIR, image_name)

    elif source == "path":
        # 绝对路径模式：用户直接输入镜像完整路径
        return validate_absolute_image_path(image_name)

    else:  # local
        validate_image_filename(image_name)
        return sanitize_path(IMAGE_DIR, image_name)


def get_rom_base_name(filename: str) -> str:
    """
    获取 ROM 包的基础名称（去除压缩后缀）

    Args:
        filename: ROM 包文件名

    Returns:
        基础名称
    """
    name_lower = filename.lower()
    double_suffixes = ['.tar.gz', '.tar.bz2', '.tar.md5', '.tgz', '.tbz2']

    for suf in double_suffixes:
        if name_lower.endswith(suf):
            return filename[:-len(suf)]

    return os.path.splitext(filename)[0]


# ======================================================================
# 模块: utils/diagnosis.py
# ======================================================================


# 错误诊断规则库
ERROR_DIAGNOSIS = [
    (r"permission denied|no permission", "USB权限不足，请先授权OTG权限（Termux弹出授权时点击允许）"),
    (r"no such partition", "分区不存在，请检查设备是否为AB分区架构，或分区名是否正确"),
    (r"device not found|no devices", "未检测到Fastboot设备，请检查：1)数据线是否连接 2)手机是否在Fastboot模式 3)OTG是否授权"),
    (r"remote: unlock device to use this command", "设备Bootloader未解锁，无法刷写。请先在开发者选项中解锁Bootloader"),
    (r"image is too large", "镜像超出分区容量，机型不匹配。请确认固件版本是否正确"),
    (r"failed to load", "镜像文件损坏或格式不正确，请重新下载固件包"),
    (r"timeout", "连接超时，请勿锁屏、保持屏幕常亮、重新插拔数据线"),
    (r"remote: security error", "校验失败，请先关闭VBmeta校验（刷入带 --disable-verity --disable-verification 的 vbmeta）"),
    (r"remote: not allowed", "操作被拒绝，请检查Bootloader锁状态，确认已解锁Bootloader"),
    (r"remote: command not allowed", "命令被拒绝，设备可能未解锁或不在正确的Fastboot模式"),
    (r"cannot read", "无法读取文件，请检查镜像文件是否存在且完整"),
    (r"unknown partition", "未知分区名，请检查分区名称是否与当前设备匹配"),
    (r"bootloader is locked", "Bootloader已锁定，请先解锁Bootloader（fastboot flashing unlock）"),
    (r"failed to erase", "擦除失败，分区可能不存在或被保护"),
    (r"write failure", "写入失败，请检查镜像是否损坏或分区是否被占用"),
    (r"not enough space|no space left", "存储空间不足，请先清理COW临时分区或释放存储空间"),
    (r"partition.*read-only|read-only partition", "分区为只读，无法写入。可能需要先禁用AVB校验"),
    (r"slot.*not found|invalid slot", "槽位不存在，请检查设备是否为AB分区架构"),
    (r"need to specify slot|requires.*slot", "需要指定槽位（-s slot），请确认设备分区类型"),
    (r"staging: open.*permission", "文件读取权限不足，请检查Termux存储权限"),
    (r"usb.*disconnect|device.*disconnect", "USB连接断开，请检查数据线是否松动"),
]


def diagnose_error(output: str) -> str:
    """
    根据错误输出自动诊断问题并给出解决建议

    Args:
        output: 命令输出（stdout/stderr）

    Returns:
        诊断结果和解决建议
    """
    if not output:
        return ""

    output_lower = output.lower()

    for pattern, tip in ERROR_DIAGNOSIS:
        if re.search(pattern, output_lower):
            logger.info(f"错误诊断匹配: {pattern} -> {tip}")
            return tip

    # 未匹配到已知错误
    return ""


def get_error_category(output: str) -> str:
    """
    获取错误类别

    Args:
        output: 命令输出

    Returns:
        错误类别 (permission/device/image/partition/unknown)
    """
    if not output:
        return "unknown"

    output_lower = output.lower()

    # 权限相关
    if re.search(r"permission|denied|not allowed", output_lower):
        return "permission"

    # 设备相关
    if re.search(r"device not found|no devices|timeout|connection", output_lower):
        return "device"

    # 镜像相关
    if re.search(r"image|failed to load|too large|cannot read|corrupt", output_lower):
        return "image"

    # 分区相关
    if re.search(r"partition|unknown|no such", output_lower):
        return "partition"

    return "unknown"


def format_diagnosis_result(error: str, diagnosis: str) -> dict:
    """
    格式化诊断结果

    Args:
        error: 原始错误信息
        diagnosis: 诊断建议

    Returns:
        格式化的诊断结果字典
    """
    return {
        "error": error,
        "diagnosis": diagnosis,
        "category": get_error_category(error),
        "has_solution": bool(diagnosis)
    }