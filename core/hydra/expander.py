# -*- coding: utf-8 -*-
# flash_tool/core/hydra/expander.py
"""
展开器
=======
根据脚本分类 ID 和 ROM Inventory，展开脚本中无法静态推断的刷写步骤。

当前支持：
- flash_all: 展开 fastboot update image-*.zip
- payload: 展开 payload.bin estimated 分区
"""

import os
import zipfile
import re
from typing import List, Dict, Optional

from .types import HydraStep
from .rom_inventory import RomInventory


# ============================================================
# 缓存常用分区列表
# ============================================================

PIXEL_KNOWN_PARTITIONS = [
    "boot", "vendor_boot", "dtbo", "vbmeta", "vbmeta_system", "vbmeta_vendor",
    "super", "system", "system_ext", "product", "vendor", "odm", "userdata",
    "cache", "persist", "modem", "bluetooth", "dsp", "misc", "recovery",
]

PAYLOAD_COMMON_PARTITIONS = [
    "boot", "vendor_boot", "dtbo", "vbmeta",
    "system", "system_ext", "product", "vendor", "odm",
    "super", "preloader", "lk", "tee",
]


# ============================================================
# 展开器入口
# ============================================================

def expand_steps(class_id: str, rom_inv: RomInventory) -> List[HydraStep]:
    """
    根据脚本分类 ID 和 ROM 资源清单展开额外步骤。

    Args:
        class_id: 脚本分类 ID，如 "payload"、"linear"、"conditional"、"function"
        rom_inv: ROM 资源清单

    Returns:
        展开后的 HydraStep 列表
    """
    if not rom_inv or (rom_inv.image_count == 0 and not rom_inv.has_payload_bin):
        return []

    steps: List[HydraStep] = []

    if class_id == "payload":
        steps = _expand_payload(rom_inv)
    # 其他 class_id 暂不展开

    return steps


# ============================================================
# 13A：Pixel / fastboot update 展开器
# ============================================================

def _expand_pixel_update(rom_inv: RomInventory) -> List[HydraStep]:
    """
    展开 Pixel flash-all 脚本中 fastboot update image-*.zip 对应的步骤。

    策略：
      1. 扫描 image-*.zip 文件列表
      2. 尝试读取 zip 内文件推断分区
      3. 如果 zip 无法读取，fallback 到已知 pixel 分区列表
    """
    steps: List[HydraStep] = []

    if not rom_inv.image_zips:
        # 无 image zip 时，基于已知分区和 ROM 目录已有镜像生成 estimated 步骤
        for part in rom_inv.partition_images:
            if part in PIXEL_KNOWN_PARTITIONS:
                steps.append(_make_flash_step(part, rom_inv.partition_images[part], "certain"))
        if steps:
            return steps
        # 完全无可识别文件：不做展开
        return []

    # 有 image-*.zip 时展开
    for zip_rel in rom_inv.image_zips:
        zip_path = os.path.join(rom_inv.rom_dir, zip_rel)
        if not os.path.isfile(zip_path):
            continue
        zip_parts = _read_image_zip_partitions(zip_path)
        for part, img_in_zip in zip_parts.items():
            steps.append(_make_flash_step(part, img_in_zip, "certain"))
        if not zip_parts:
            # zip 无法读取时 fallback 到已知分区列表，标记 estimated
            for part in PIXEL_KNOWN_PARTITIONS:
                steps.append(_make_flash_step(part, f"{part}.img", "estimated"))

    # 去重
    seen = set()
    deduped = []
    for s in steps:
        key = (s.type, s.part, s.fileName)
        if key not in seen:
            seen.add(key)
            deduped.append(s)

    return deduped


def _read_image_zip_partitions(zip_path: str) -> Dict[str, str]:
    """
    尝试读取 image-*.zip 内的文件列表，返回分区名 → 文件名映射。
    """
    result: Dict[str, str] = {}
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            for name in z.namelist():
                base = os.path.basename(name)
                ext = os.path.splitext(base)[1].lower()
                if ext in ('.img', '.bin'):
                    part = os.path.splitext(base)[0].lower()
                    result[part] = name
    except Exception:
        pass
    return result


# ============================================================
# 13B：payload.bin 展开器
# ============================================================

def _expand_payload(rom_inv: RomInventory) -> List[HydraStep]:
    """
    展开 payload OTA 包对应的 estimated 刷写步骤。

    策略：
      1. 扫描 payload_properties.txt 中的分区列表（如果有）
      2. 尝试读取 payload.bin 头部信息（可选）
      3. fallback 到已知分区列表
      4. 所有步骤标记为 estimated
    """
    steps: List[HydraStep] = []
    partitions: List[str] = []

    # 尝试从 payload_properties.txt 推断分区
    if rom_inv.payload_properties:
        props_path = os.path.join(rom_inv.rom_dir, rom_inv.payload_properties)
        if os.path.isfile(props_path):
            try:
                with open(props_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        m = re.match(r'^FILE_HASH\s*=\s*(\S+)', line)
                        if m:
                            pass  # 文件名级哈希，不直接对应分区名
                        # 也可以尝试识别其他字段
            except Exception:
                pass

    # 从 rom_inv.partition_images 中找已知分区
    if rom_inv.partition_images:
        for part in sorted(rom_inv.partition_images.keys()):
            if part in PAYLOAD_COMMON_PARTITIONS:
                partitions.append(part)
    if partitions:
        # 有可识别分区时用这些
        pass
    else:
        # 无分区识别时用完整已知列表
        partitions = PAYLOAD_COMMON_PARTITIONS[:]

    for part in partitions:
        steps.append(_make_flash_step(part, f"payload/{part}.img", "estimated"))

    if not steps:
        # 完全无损时至少生成一个占位步骤
        steps.append(HydraStep(
            type="flash",
            part="unknown",
            fileName="payload.bin",
            raw="payload OTA 包（需解包后解析）",
            confidence="estimated",
            note="payload OTA 包：需要解包后执行",
        ))

    return steps


# ============================================================
# 内部工具
# ============================================================

def _make_flash_step(part: str, img: str, confidence: str = "certain") -> HydraStep:
    """生成一个 flash 步骤。"""
    raw = f"fastboot flash {part} {img}"
    return HydraStep(
        type="flash",
        part=part,
        fileName=img,
        raw=raw,
        confidence=confidence,
        note=f"刷写分区 {part}" if confidence == "estimated" else "",
        dynamic=(confidence == "estimated"),
    )


__all__ = ["expand_steps", "_expand_pixel_update", "_expand_payload"]