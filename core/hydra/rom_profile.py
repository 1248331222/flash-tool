# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/rom_profile.py
"""
Hydra — ROM Profile 分类器
==========================
基于 RomInventory 判断 ROM 包的类型、平台、刷机模式要求。

核心概念：
    - rom_flavor: 刷机方式风格（payload / fastboot / raw / mtk-brom / qcom-emmc）
    - platform:   平台系列（qcom / mtk / exynos / generic）
    - security_level: 安全等级（signed / verified / locked / unlocked）
    - slot_scheme:  A/B 槽方案（ab / a-only / virtual-ab）
    - mode_required: 刷机需要的模式指令（"flash" / "boot" / "update" 等）

用法：
    from core.hydra.rom_profile import profile_rom

    profile = profile_rom(inv)
    print(profile.rom_flavor, profile.platform, profile.slot_scheme)
"""

import os
import re
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field

from .rom_inventory import RomInventory


# ============================================================
# 分区名 → 平台 / 类型 推断
# ============================================================

# Qualcomm 特有分区
QCOM_PARTITIONS = {
    "xbl", "xbl_config", "tz", "hyp", "abl",
    "cmnlib", "cmnlib64", "keymaster", "qupfw",
    "devcfg", "storsec", "logfs", "system_ram",
    "mdtp", "mdtpsecapp", "dsp", "misc",
    "non-hlos", "btfm", "modem", "oem", "minidump",
}

# MTK 特有分区
MTK_PARTITIONS = {
    "preloader", "preloader_", "lk", "lk_",
    "tee", "tee1", "tee2", "scp", "md1img",
    "md1rom", "md1dsp", "md1arm7", "gz",
    "mcupm", "spmfw", "sspm", "dpm", "vpu",
}

# A/B 槽分区模式
AB_PARTITIONS = {
    "boot_a", "boot_b",
    "system_a", "system_b",
    "vendor_a", "vendor_b",
    "product_a", "product_b",
    "vbmeta_a", "vbmeta_b",
    "dtbo_a", "dtbo_b",
    "super_a", "super_b",
    "userdata_a", "userdata_b",
}

# payload.bin 相关的分区特征
PAYLOAD_PARTITIONS = {
    "system", "vendor", "product", "odm",
    "system_ext", "system_other",
    "boot", "dtbo", "vbmeta", "vbmeta_system",
    "super", "userdata", "cache", "cust",
}

# 固件特征文件
FIRMWARE_MARKERS = {
    "NON-HLOS.bin",
    "BTFM.bin",
    "dspso.bin",
    "preloader",
    "lk.bin",
    "tee.bin",
    "scp.bin",
}


# ============================================================
# RomProfile — 数据类
# ============================================================

@dataclass
class RomProfile:
    """ROM 包结构识别结果"""
    # 刷机风格
    rom_flavor: str = "unknown"          # payload / fastboot / raw / mtk-brom / qcom-emmc

    # 平台信息
    platform: str = "unknown"            # qcom / mtk / exynos / generic

    # 槽方案
    slot_scheme: str = "unknown"         # a-only / ab / virtual-ab

    # 安全等级
    security_level: str = "unknown"      # signed / verified / unlocked

    # 所需刷机模式
    mode_required: str = "flash"         # flash / boot / update / brom

    # 额外说明
    notes: List[str] = field(default_factory=list)

    # 特征子项（调试用）
    partition_pattern_hits: List[str] = field(default_factory=list)

    # 期望文件清单
    required_files: List[str] = field(default_factory=list)

    # 资源完整性
    missing_critical: List[str] = field(default_factory=list)   # 缺失的关键文件
    integrity_notes: List[str] = field(default_factory=list)    # 完整性说明

    has_payload: bool = False
    has_image_zip: bool = False
    has_android_info: bool = False
    has_preloader: bool = False
    has_firmware: bool = False


# ============================================================
# 平台探测
# ============================================================

def _detect_platform(inv: RomInventory) -> Tuple[str, List[str]]:
    """
    基于分区名判断平台。
    返回 (platform, hits)。
    """
    hits: List[str] = []
    parts = set(inv.partition_images.keys())

    # Qualcomm 匹配
    qcom_hits = parts & QCOM_PARTITIONS
    if qcom_hits:
        hits.append(f"qcom_partitions={sorted(qcom_hits)}")

    # MTK 匹配
    mtk_hits = parts & MTK_PARTITIONS
    if mtk_hits:
        hits.append(f"mtk_partitions={sorted(mtk_hits)}")

    # 特殊文件名匹配
    for f in inv.flashable_files:
        base = os.path.basename(f).lower()
        if base in ('non-hlos.bin', 'btfm.bin', 'dspso.bin'):
            hits.append(f"qcom_firmware={base}")
        if base.startswith('preloader'):
            hits.append(f"mtk_firmware={base}")

    if len(qcom_hits) >= 2 or any('xbl' in p for p in parts):
        return "qcom", hits
    if len(mtk_hits) >= 2 or inv.has_preloader:
        return "mtk", hits

    # 模糊匹配：有固件但不是明显 qcom/mtk → generic
    if hits:
        return "generic", hits

    return "unknown", hits


def _detect_slot_scheme(inv: RomInventory) -> str:
    """判断 A/B 槽方案"""
    parts = set(inv.partition_images.keys())

    # 检查是否有 _a/_b 后缀
    has_ab = any(p.endswith('_a') or p.endswith('_b') for p in parts)
    if has_ab:
        return "ab"

    # 检查是否是 virtual-ab（有 system 但无 boot_a）
    if 'system' in parts and 'vendor' in parts:
        return "a-only"

    return "a-only"


def _detect_flavor(inv: RomInventory) -> str:
    """判断刷机风格"""

    # payload.bin → OTA 式刷机
    if inv.has_payload_bin:
        return "payload"

    # image-*.zip → 多镜像打包
    if inv.has_image_zip:
        return "fastboot"

    # android-info.txt → Pixel/AOSP fastboot 包
    if inv.has_android_info:
        return "fastboot"

    # 有 preloader → MTK BROM 刷机
    if inv.has_preloader:
        return "mtk-brom"

    # 有大量分区镜像
    if inv.partition_count >= 3:
        return "fastboot"

    # 有固件但分区少 → qcom-emmc
    if inv.has_firmware and inv.partition_count <= 2:
        return "qcom-emmc"

    return "unknown"


def _detect_security(inv: RomInventory) -> str:
    """安全等级推断（基于可用信息给出初始判定）"""
    if inv.has_payload_bin:
        return "signed"  # payload.bin 通常已签名
    if inv.has_android_info:
        return "verified"  # 官方 AOSP 包
    if inv.has_preloader:
        return "locked"  # MTK 通常上锁
    if inv.has_firmware:
        return "unlocked"  # 第三方/非官方固件
    return "unknown"


# ============================================================
# 资源完整性检查
# ============================================================

# 平台特有期望文件（分区名 → 说明）
_QCOM_EXPECTED = [
    ("boot.img", "启动镜像"),
    ("vbmeta.img", "签名验证（VBMeta）"),
    ("NON-HLOS.bin", "基带/无线固件（Qualcomm）"),
    ("BTFM.bin", "蓝牙固件"),
    ("dspso.bin", "DSP 固件"),
    ("xbl.elf", "XBL 引导加载器"),
    ("tz.mbn", "TrustZone 固件"),
    ("abl.elf", "ABL 引导加载器"),
    ("hyp.mbn", "Hypervisor 固件"),
]

_MTK_EXPECTED = [
    ("boot.img", "启动镜像"),
    ("vbmeta.img", "签名验证（VBMeta）"),
    ("preloader", "Preloader 引导加载器"),
    ("lk.bin", "LK 引导加载器（Little Kernel）"),
    ("tee.bin", "Trusted Execution Environment 固件"),
    ("scp.bin", "SCP 固件（System Control Processor）"),
    ("md1img.bin", "基带固件（Modem）"),
    ("spmfw.bin", "SPM 固件（System Power Manager）"),
]

_GENERIC_EXPECTED = [
    ("boot.img", "启动镜像"),
    ("vbmeta.img", "签名验证（VBMeta）"),
]


def check_integrity(profile: RomProfile, inv: RomInventory) -> None:
    """
    基于 ROM Profile 检查资源完整性。
    结果写入 profile.missing_critical / profile.integrity_notes。
    """
    profile.missing_critical.clear()
    profile.integrity_notes.clear()

    # 获取所有可刷写文件的 basename（小写），方便模糊匹配
    flashable_basenames = set()
    for f in inv.flashable_files:
        base = os.path.basename(f).lower()
        flashable_basenames.add(base)

    # 辅助函数：检查某文件是否存在（前缀匹配）
    def _has(target: str) -> bool:
        t = target.lower()
        # 精确匹配（如 boot.img）
        if t in flashable_basenames:
            return True
        # 前缀匹配（如 preloader → preloader_xxx.bin）
        return any(b.startswith(t) or t.startswith(b) for b in flashable_basenames)

    # 按平台选择期望清单
    if profile.platform == "qcom":
        expected_list = _QCOM_EXPECTED
    elif profile.platform == "mtk":
        expected_list = _MTK_EXPECTED
    else:
        expected_list = _GENERIC_EXPECTED

    for fname, desc in expected_list:
        # 对特定平台，有些文件不是强制要求（如 MTK 不需要 NON-HLOS）
        if profile.platform == "mtk" and fname in ("NON-HLOS.bin", "BTFM.bin", "dspso.bin", "xbl.elf", "tz.mbn", "abl.elf", "hyp.mbn"):
            continue
        if profile.platform == "qcom" and fname in ("preloader", "lk.bin", "tee.bin", "scp.bin", "md1img.bin", "spmfw.bin"):
            continue

        if not _has(fname):
            profile.missing_critical.append(f"{fname}（{desc}）")

    # payload 包的额外检查
    if profile.has_payload:
        if not inv.payload_properties:
            profile.missing_critical.append("payload_properties.txt（刷写参数）")

    # 完整性总结 note
    if profile.missing_critical:
        profile.integrity_notes.append(
            f"缺少 {len(profile.missing_critical)} 个关键文件：{', '.join(profile.missing_critical[:3])}"
            + (f" 等 {len(profile.missing_critical)} 个" if len(profile.missing_critical) > 3 else "")
        )
    else:
        profile.integrity_notes.append("所有期望的关键文件均已找到")


def _detect_required_files(inv: RomInventory) -> List[str]:
    """期望的关键文件（平台特有）"""
    required = []

    # payload 方案
    if inv.has_payload_bin:
        required.append("payload.bin")
        if not inv.payload_properties:
            required.append("payload_properties.txt")

    # fastboot 方案
    if not inv.has_payload_bin and not inv.has_image_zip:
        for essential in ("boot.img", "system.img", "vbmeta.img"):
            if not any(essential in f.lower() for f in inv.flashable_files):
                required.append(essential)

    # 固件文件
    for fw in ("NON-HLOS.bin", "BTFM.bin", "preloader"):
        if any(fw.lower() in f.lower() for f in inv.flashable_files):
            continue
        # 如果存在其他同平台固件，需要检查
        if inv.has_firmware:
            pass

    return required


# ============================================================
# 主入口
# ============================================================

def profile_rom(inv: RomInventory) -> RomProfile:
    """
    对 ROM Inventory 进行分类分析。

    Args:
        inv: RomInventory（scan_rom 的输出）

    Returns:
        RomProfile
    """
    profile = RomProfile()

    if not inv.flashable_files and not inv.has_payload_bin and not inv.has_image_zip:
        profile.notes.append("ROM 目录中未发现可刷写文件")
        return profile

    # 基本标记
    profile.has_payload = inv.has_payload_bin
    profile.has_image_zip = inv.has_image_zip
    profile.has_android_info = inv.has_android_info

    # 检查 preloader
    profile.has_preloader = any(
        'preloader' in os.path.basename(f).lower()
        for f in inv.flashable_files
    )

    # 检查固件
    profile.has_firmware = len(inv.firmware_files) > 0
    if not profile.has_firmware:
        profile.has_firmware = any(
            os.path.basename(f).lower() in {n.lower() for n in FIRMWARE_MARKERS}
            for f in inv.flashable_files
        )

    # 平台探测
    profile.platform, hits = _detect_platform(inv)
    profile.partition_pattern_hits = hits

    # 槽方案
    profile.slot_scheme = _detect_slot_scheme(inv)

    # 刷机风格
    profile.rom_flavor = _detect_flavor(inv)

    # 安全等级
    profile.security_level = _detect_security(inv)

    # 模式要求
    if profile.rom_flavor == "payload":
        profile.mode_required = "update"
    elif profile.rom_flavor == "mtk-brom":
        profile.mode_required = "brom"
    else:
        profile.mode_required = "flash"

    # 期望文件
    profile.required_files = _detect_required_files(inv)

    # 资源完整性检查
    check_integrity(profile, inv)

    # 额外说明
    if profile.has_payload:
        profile.notes.append("payload.bin 格式：适用于 OTA/update 刷机")
    if profile.has_image_zip:
        profile.notes.append("image-*.zip 格式：需解压后刷写")
    if profile.has_android_info:
        profile.notes.append("android-info.txt：AOSP fastboot 包")
    if profile.platform == "qcom":
        profile.notes.append("Qualcomm 平台：注意 NDH（Non-HLOS）固件完整性")
    elif profile.platform == "mtk":
        profile.notes.append("MediaTek 平台：注意 preloader 和 DA 文件")
    if profile.slot_scheme == "ab":
        profile.notes.append("A/B 槽：刷写时指定当前槽位")

    return profile


def profile_rom_from_dir(rom_dir: str) -> RomProfile:
    """
    从 ROM 目录路径直接生成 Profile。

    Args:
        rom_dir: ROM 包目录

    Returns:
        RomProfile
    """
    from .rom_inventory import scan_rom
    inv = scan_rom(rom_dir)
    return profile_rom(inv)


__all__ = [
    "RomProfile",
    "profile_rom",
    "profile_rom_from_dir",
    "check_integrity",
]