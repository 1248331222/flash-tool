# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/rom_inventory.py
"""
Hydra — ROM 包资源扫描器
=========================
扫描 ROM 目录中的镜像文件、payload.bin、android-info.txt 等资源，
输出一份标准化的 ROM Inventory 供各模块共享使用。
"""

import os
import glob as glob_mod
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field

import fnmatch


# ============================================================
# 常见镜像目录名
# ============================================================

IMAGE_DIR_NAMES = {"images", "image", "Images", "IMAGES", "img", "IMG"}

# 常见可刷写文件扩展名（最终用户可指定的都是可刷写文件）
FLASHABLE_EXTENSIONS = {".img", ".bin", ".elf", ".mbn",}

# 常见只 bin 文件的平台（MTK preloader 等）
BIN_SPECIFIC = {"preloader", "lk", "tee", "scp"}

# 固件/底层分区命名模式（不一定是 .img，也常见 .bin/.mbn/.elf）
FIRMWARE_PARTITIONS = {
    "modem", "NON-HLOS", "BTFM", "dsp", "dspso",
    "xbl", "xbl_config", "tz", "hyp", "abl",
    "cmnlib", "cmnlib64", "keymaster", "qupfw",
    "devcfg", "storsec", "md1img", "md1rom",
    "spmfw", "sspm", "scp", "mcupm",
    "preloader", "lk", "tee", "gz",
}


# ============================================================
# RomInventory — 数据类
# ============================================================

@dataclass
class RomInventory:
    """ROM 包目录的完整资源清单"""
    rom_dir: str = ""
    image_dirs: List[str] = field(default_factory=list)         # 找到的镜像目录路径

    # 统一可刷写文件清单（.img / .bin / .mbn / .elf）
    flashable_files: List[str] = field(default_factory=list)    # 所有可刷写文件（相对路径）
    partition_images: Dict[str, str] = field(default_factory=dict)  # 分区名 → 路径映射

    # 固件相关文件（modem/dsp/bluetooth 等）
    firmware_files: List[str] = field(default_factory=list)      # 固件文件列表

    # 压缩包
    zip_files: List[str] = field(default_factory=list)           # .zip 文件列表

    # 特化文件
    payload_bin: str = ""                                        # payload.bin 路径
    payload_properties: str = ""                                 # payload_properties.txt 路径
    android_info: str = ""                                       # android-info.txt 路径
    image_zips: List[str] = field(default_factory=list)          # image-*.zip 列表

    # 布尔标记
    has_payload_bin: bool = False
    has_android_info: bool = False
    has_image_zip: bool = False
    has_firmware: bool = False          # 是否有固件文件（NON-HLOS/BTFM/dspso/preloader 等）
    has_preloader: bool = False         # 是否有 preloader 文件（MTK 特征）

    # 统计
    image_count: int = 0
    partition_count: int = 0

    # （向后兼容）旧字段，方便逐步迁移
    @property
    def image_files(self) -> List[str]:
        """向下兼容：.img 文件列表"""
        return [f for f in self.flashable_files if f.lower().endswith('.img')]

    @property
    def bin_files(self) -> List[str]:
        """向下兼容：.bin 文件列表"""
        return [f for f in self.flashable_files if f.lower().endswith('.bin')]

    @property
    def available_images(self) -> List[str]:
        """向下兼容：所有可用的闪存文件名（不含路径）"""
        seen: Set[str] = set()
        result = []
        for f in self.flashable_files:
            base = os.path.basename(f).lower()
            if base not in seen:
                seen.add(base)
                result.append(base)
        return result


# ============================================================
# 扫描函数
# ============================================================

def scan_rom(rom_dir: str) -> RomInventory:
    """
    扫描 ROM 目录，返回 RomInventory。

    Args:
        rom_dir: ROM 包根目录。

    Returns:
        RomInventory
    """
    inv = RomInventory(rom_dir=rom_dir)

    if not rom_dir or not os.path.isdir(rom_dir):
        return inv

    rom_abs = os.path.abspath(rom_dir)

    # 1. 查找镜像目录
    for d in IMAGE_DIR_NAMES:
        full = os.path.join(rom_abs, d)
        if os.path.isdir(full):
            inv.image_dirs.append(full)

    # 搜索范围：rom 根目录 + 所有镜像子目录
    search_dirs = [rom_abs] + list(inv.image_dirs)

    # 2. 扫描根目录 zip 文件
    for f in sorted(os.listdir(rom_abs)):
        fpath = os.path.join(rom_abs, f)
        if not os.path.isfile(fpath):
            continue
        ext = os.path.splitext(f)[1].lower()
        if ext == ".zip":
            rel_path = os.path.relpath(fpath, rom_abs)
            inv.zip_files.append(rel_path)

    # 3. 扫描可刷写文件（统一 .img / .bin / .mbn / .elf）
    seen_partitions: Set[str] = set()
    seen_filenames: Set[str] = set()

    for base_dir in search_dirs:
        if not os.path.isdir(base_dir):
            continue
        for f in sorted(os.listdir(base_dir)):
            fpath = os.path.join(base_dir, f)
            if not os.path.isfile(fpath):
                continue
            ext = os.path.splitext(f)[1].lower()
            name_no_ext = os.path.splitext(f)[0].lower()

            if ext in FLASHABLE_EXTENSIONS:
                rel_path = os.path.relpath(fpath, rom_abs)
                # 去重
                if rel_path.lower() in seen_filenames:
                    continue
                seen_filenames.add(rel_path.lower())

                inv.flashable_files.append(rel_path)
                inv.image_count += 1

                # 分区名推断（去空格修饰）
                part = name_no_ext.strip().strip('_').strip('-')

                # 固件文件单独归类
                base_lower = f.lower()
                is_fw = any(fw in base_lower for fw in ('non-hlos', 'btfm', 'dsp', 'modem', 'preloader'))
                if is_fw:
                    inv.firmware_files.append(rel_path)
                    inv.has_firmware = True
                if 'preloader' in base_lower:
                    inv.has_preloader = True

                # 加入分区映射
                if part not in seen_partitions:
                    seen_partitions.add(part)
                    inv.partition_images[part] = rel_path
                    inv.partition_count += 1

            elif ext == ".zip":
                # 在子目录中发现的 zip 也加入
                rel_path = os.path.relpath(fpath, rom_abs)
                if rel_path not in inv.zip_files:
                    inv.zip_files.append(rel_path)

    # 4. 特殊文件检查
    payload_path = os.path.join(rom_abs, "payload.bin")
    if os.path.isfile(payload_path):
        inv.payload_bin = "payload.bin"
        inv.has_payload_bin = True
        # payload.bin 也加入 flashable_files（如果还没加入）
        if "payload.bin" not in [f.lower() for f in inv.flashable_files]:
            inv.flashable_files.append("payload.bin")
            inv.image_count += 1

    props_path = os.path.join(rom_abs, "payload_properties.txt")
    if os.path.isfile(props_path):
        inv.payload_properties = "payload_properties.txt"

    android_info_path = os.path.join(rom_abs, "android-info.txt")
    if os.path.isfile(android_info_path):
        inv.android_info = "android-info.txt"
        inv.has_android_info = True

    # 5. image-*.zip
    for zf in inv.zip_files:
        zname = os.path.basename(zf).lower()
        if zname.startswith("image-") and zname.endswith(".zip"):
            inv.image_zips.append(zf)
            inv.has_image_zip = True

    return inv


# ============================================================
# 工具函数
# ============================================================

def find_image(partition: str, inv: RomInventory) -> Optional[str]:
    """查找指定分区的镜像文件路径（相对 rom_dir）。"""
    p = partition.lower().strip().strip('"').strip("'")
    return inv.partition_images.get(p)


def has_image(partition: str, inv: RomInventory) -> bool:
    """判断指定分区是否有镜像文件。"""
    return find_image(partition, inv) is not None


def resolve_path(path: str, script_dir: str = "", rom_dir: str = "") -> str:
    """
    统一路径解析：先作为绝对路径，再尝试 script_dir，最后 rom_dir。
    """
    if os.path.isabs(path):
        return path
    if script_dir:
        candidate = os.path.join(script_dir, path)
        if os.path.exists(candidate):
            return candidate
    if rom_dir:
        candidate = os.path.join(rom_dir, path)
        if os.path.exists(candidate):
            return candidate
    # fallback 到 script_dir + path
    if script_dir:
        return os.path.join(script_dir, path)
    return path


def resolve_glob(pattern: str, script_dir: str = "", rom_dir: str = "") -> List[str]:
    """
    统一 glob 解析：支持 script_dir 和 rom_dir 双路径搜索。
    """
    results = []
    if script_dir:
        full = pattern
        if not os.path.isabs(full):
            full = os.path.join(script_dir, pattern)
        results.extend(glob_mod.glob(full))
    if rom_dir and rom_dir != script_dir:
        full = pattern
        if not os.path.isabs(full):
            full = os.path.join(rom_dir, pattern)
        results.extend(glob_mod.glob(full))
    return sorted(set(results))


def normalize_windows_path(path: str) -> str:
    """统一 Windows 路径分隔符。"""
    return path.replace("\\\\", "/").replace("\\", "/")


__all__ = [
    "RomInventory",
    "scan_rom",
    "find_image",
    "has_image",
    "resolve_path",
    "resolve_glob",
    "normalize_windows_path",
]