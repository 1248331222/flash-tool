# -*- coding: utf-8 -*-
# flash_tool/core/hydra/case_profile.py
"""
Hydra — Case Profile 适配器
============================
基于 HydraParseResult + RomInventory + RomProfile，判断刷机包的风格归属。

核心能力：
    1. 识别厂商家族（小米 / Pixel / OPPO / MTK 通用等）
    2. 识别工具生态（fastboot-bat / fastboot-sh / payload-ota / mtk-brom 等）
    3. 识别案例类型（factory_fastboot_rom / ota_payload / firmware_package 等）
    4. 给出置信度 + 信号列表

用法：
    from core.hydra.case_profile import detect_case_profile

    profile = detect_case_profile(result, rom_inv, rom_profile)
    print(profile.vendor_family, profile.tool_family, profile.case_type)
"""

import os
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


# ============================================================
# CaseProfile — 数据类
# ============================================================

@dataclass
class CaseProfile:
    """刷机包案例特征识别结果"""
    vendor_family: str = "unknown"       # xiaomi / pixel / oneplus / oppo / mtk_generic / huawei / samsung / unknown
    tool_family: str = "unknown"         # fastboot-bat / fastboot-sh / payload-ota / mtk-brom / heimdall / unknown
    case_type: str = "unknown"           # factory_fastboot_rom / ota_payload / firmware_package / user_bundle / unknown
    confidence: float = 0.0              # 0.0 ~ 1.0
    signals: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vendor_family": self.vendor_family,
            "tool_family": self.tool_family,
            "case_type": self.case_type,
            "confidence": round(self.confidence, 2),
            "signals": self.signals,
            "notes": self.notes,
        }


# ============================================================
# 信号检查辅助
# ============================================================

def _has_script(result: Any, *names: str) -> bool:
    """检查脚本文件名是否匹配某个模式"""
    # 从 result 能拿到的脚本名
    path = getattr(result, 'script_path', None) or ''
    basename = os.path.basename(path).lower()
    any_match = any(
        basename == n.lower() or basename.startswith(n.lower().rstrip('*'))
        for n in names
    )
    if any_match:
        return True
    # 从 content 检查文件名模式（兜底：查看 script_type + 内容）
    # 这里不检查内容，由上层 detect 函数负责
    return False


def _step_count_by(result: Any, part_pattern: Optional[str] = None,
                    confidence: Optional[str] = None) -> int:
    """统计符合条件的步骤数"""
    count = 0
    for step in getattr(result, 'steps', []) or []:
        if part_pattern and not re.search(part_pattern, getattr(step, 'part', '') or '', re.I):
            continue
        if confidence and getattr(step, 'confidence', '') != confidence:
            continue
        count += 1
    return count


def _has_file(inv: Any, *patterns: str) -> bool:
    """检查 ROM inventory 中是否有匹配的文件"""
    for f in getattr(inv, 'flashable_files', []) or []:
        base = os.path.basename(f).lower()
        for p in patterns:
            if p.lower() in base:
                return True
    return False


def _has_partition(inv: Any, *names: str) -> bool:
    """检查 ROM inventory 中是否有匹配的分区名"""
    parts = getattr(inv, 'partition_images', {}) or {}
    for p in parts:
        pl = p.lower()
        for n in names:
            if n.lower() in pl:
                return True
    return False


def _has_firmware_named(inv: Any, *patterns: str) -> bool:
    """检查固件文件中是否有匹配的"""
    for f in getattr(inv, 'firmware_files', []) or []:
        base = os.path.basename(f).lower()
        for p in patterns:
            if p.lower() in base:
                return True
    return False


# ============================================================
# 各检测器
# ============================================================

def _detect_xiaomi(result: Any, inv: Any, rp: Any) -> Optional[CaseProfile]:
    """检测是否为小米 fastboot 线刷包"""
    signals: List[str] = []
    score = 0.0

    # 小米特有分区
    if _has_partition(inv, 'cust'):
        signals.append("检测到 cust 分区（小米特有）")
        score += 0.25

    if _has_partition(inv, 'vendor_boot'):
        signals.append("检测到 vendor_boot 分区")
        score += 0.05

    if _has_partition(inv, 'vbmeta_system'):
        signals.append("检测到 vbmeta_system 分区")
        score += 0.05

    # 小米特有脚本命名
    path = getattr(result, 'script_path', '') or ''
    name = os.path.basename(path).lower()
    if name in ('flash_all.bat', 'flash_all_lock.bat'):
        signals.append(f"检测到 {name}（小米专用）")
        score += 0.25
    elif name in ('flash_all_except_data_storage.bat', 'flash_all_except_data.bat'):
        signals.append(f"检测到 {name}（小米用户数据保留脚本）")
        score += 0.20

    # 小米常用固件
    if _has_firmware_named(inv, 'NON-HLOS.bin'):
        signals.append("检测到 Qualcomm 固件 NON-HLOS.bin")
        score += 0.10

    # 分区数量特征（小米 fastboot 包通常 15+ 个分区）
    inv_part_count = getattr(inv, 'partition_count', 0) or 0
    if inv_part_count >= 15:
        signals.append(f"包含 {inv_part_count} 个分区（完整 fastboot 包）")
        score += 0.10

    # 风格：fastboot.bat 类型
    if rp and getattr(rp, 'rom_flavor', '') == 'fastboot':
        signals.append("ROM 类型为 fastboot 刷机")
        score += 0.10

    if score < 0.3:
        return None

    profile = CaseProfile(
        vendor_family="xiaomi",
        tool_family="fastboot-bat",
        case_type="factory_fastboot_rom",
        confidence=min(score + 0.1, 0.95),
        signals=signals,
    )
    # 检查是否有锁/保护脚本
    if 'lock' in name:
        profile.notes.append("包含 flash_all_lock.bat，刷机后会自动上锁引导加载器")
    if 'except_data' in name:
        profile.notes.append("包含保留用户数据刷机脚本")
    return profile


def _detect_pixel(result: Any, inv: Any, rp: Any) -> Optional[CaseProfile]:
    """检测是否为 Pixel / Google factory image 刷机包"""
    signals: List[str] = []
    score = 0.0

    # Pixel 特有脚本名
    path = getattr(result, 'script_path', '') or ''
    name = os.path.basename(path).lower()
    if name in ('flash-all.sh', 'flash-all.bat'):
        signals.append(f"检测到 {name}（Pixel 标准刷机脚本）")
        score += 0.25

    # android-info.txt（AOSP 官方包特征）
    if rp and getattr(rp, 'has_android_info', False):
        signals.append("包含 android-info.txt（AOSP 官方包）")
        score += 0.20

    # image-*.zip（Pixel 打包格式）
    if rp and getattr(rp, 'has_image_zip', False):
        signals.append("包含 image-*.zip（Pixel factory image 格式）")
        score += 0.20

    # bootloader-*.img / radio-*.img（Pixel 特有）
    if _has_file(inv, 'bootloader-', 'radio-'):
        signals.append("检测到 bootloader-*.img / radio-*.img")
        score += 0.15

    # 分区特征（Pixel 通常有 bootloader_X 等）
    if rp and getattr(rp, 'rom_flavor', '') == 'fastboot':
        signals.append("ROM 类型为 fastboot 刷机")
        score += 0.05

    # 脚本类型
    script_type = getattr(result, 'script_type', '')
    if script_type == 'sh':
        signals.append("脚本类型为 shell (sh)")
        score += 0.05

    if score < 0.3:
        return None

    profile = CaseProfile(
        vendor_family="pixel",
        tool_family="fastboot-sh" if script_type == 'sh' else "fastboot-bat",
        case_type="factory_fastboot_rom",
        confidence=min(score + 0.1, 0.95),
        signals=signals,
    )
    if rp and getattr(rp, 'has_android_info', False):
        profile.notes.append("标准 AOSP fastboot 刷机流程，可通过 fastboot update 刷入")
    return profile


def _detect_payload_ota(result: Any, inv: Any, rp: Any) -> Optional[CaseProfile]:
    """检测是否为 payload OTA 更新包"""
    signals: List[str] = []
    score = 0.0

    if rp and getattr(rp, 'has_payload', False):
        signals.append("包含 payload.bin（OTA 更新格式）")
        score += 0.35

    if inv and getattr(inv, 'has_payload_bin', False):
        signals.append("ROM 资源中检测到 payload.bin")
        score += 0.20

    if inv and getattr(inv, 'payload_properties', None):
        signals.append("包含 payload_properties.txt（刷写参数）")
        score += 0.15

    # 脚本类型（payload 通常搭配 .sh 或 .py）
    script_type = getattr(result, 'script_type', '')
    if script_type == 'sh':
        signals.append("脚本类型为 shell (sh)")
        score += 0.05
    elif script_type == 'bat':
        score += 0.02

    if score < 0.3:
        return None

    tool_fam = "payload-ota"
    if rp and getattr(rp, 'rom_flavor', '') == 'payload':
        tool_fam = "payload-ota"

    profile = CaseProfile(
        vendor_family="generic",
        tool_family=tool_fam,
        case_type="ota_payload",
        confidence=min(score + 0.1, 0.95),
        signals=signals,
    )
    profile.notes.append("OTA payload 包，适用于 recovery / update 刷机模式")
    return profile


def _detect_qcom_firmware(result: Any, inv: Any, rp: Any) -> Optional[CaseProfile]:
    """检测是否为 Qualcomm 通用固件包（firmware-only，含 xbl/tz/abl 等）"""
    signals: List[str] = []
    score = 0.0

    if rp and getattr(rp, 'platform', '') == 'qcom':
        signals.append("Qualcomm 平台识别")
        score += 0.20

    # 检查 Qualcomm 特有固件文件
    qcom_fw_count = 0
    for f in getattr(inv, 'firmware_files', []) or []:
        base = os.path.basename(f).lower()
        if base in ('non-hlos.bin', 'btfm.bin', 'dspso.bin'):
            qcom_fw_count += 1

    if qcom_fw_count >= 2:
        signals.append(f"检测到 {qcom_fw_count} 个 Qualcomm 固件文件")
        score += 0.20
    elif qcom_fw_count >= 1:
        signals.append("检测到 Qualcomm 固件文件")
        score += 0.10

    # 检查特定引导文件
    if _has_file(inv, 'xbl.', 'abl.', 'tz.'):
        signals.append("检测到 XBL/ABL/TZ 引导加载器")
        score += 0.20

    # 分区少，固件多 → firmware-only 包
    inv_part_count = getattr(inv, 'partition_count', 0) or 0
    fw_count = len(getattr(inv, 'firmware_files', []) or [])
    if inv_part_count <= 3 and fw_count >= 3:
        signals.append(f"分区少({inv_part_count})但固件多({fw_count})，疑似纯固件包")
        score += 0.15

    if score < 0.3:
        return None

    profile = CaseProfile(
        vendor_family="qcom_generic",
        tool_family="fastboot-bat",
        case_type="firmware_package",
        confidence=min(score + 0.1, 0.95),
        signals=signals,
    )
    profile.notes.append("Qualcomm 固件包，含底层引导加载器和无线固件")
    return profile


def _detect_mtk_firmware(result: Any, inv: Any, rp: Any) -> Optional[CaseProfile]:
    """检测是否为 MTK 通用固件包"""
    signals: List[str] = []
    score = 0.0

    if rp and getattr(rp, 'platform', '') == 'mtk':
        signals.append("MediaTek 平台识别")
        score += 0.20

    if rp and getattr(rp, 'has_preloader', False):
        signals.append("包含 preloader（MTK 引导加载器）")
        score += 0.25

    # MTK 特有固件
    mtk_fw = 0
    for f in getattr(inv, 'flashable_files', []) or []:
        base = os.path.basename(f).lower()
        if base in ('lk.bin', 'tee.bin', 'scp.bin', 'md1img.bin', 'spmfw.bin'):
            mtk_fw += 1
        if base.startswith('preloader'):
            mtk_fw += 1

    if mtk_fw >= 3:
        signals.append(f"检测到 {mtk_fw} 个 MTK 固件文件")
        score += 0.20
    elif mtk_fw >= 1:
        signals.append("检测到 MTK 固件文件")
        score += 0.10

    # 检查 scatter.txt（MTK 特有）
    if _has_file(inv, 'scatter.txt'):
        signals.append("包含 scatter.txt（MTK 分区描述文件）")
        score += 0.15

    # 脚本命名
    path = getattr(result, 'script_path', '') or ''
    name = os.path.basename(path).lower()
    if name in ('flash_tool.bat', 'download.bat'):
        signals.append(f"检测到 {name}（MTK 刷机专用脚本）")
        score += 0.15

    if score < 0.3:
        return None

    profile = CaseProfile(
        vendor_family="mtk_generic",
        tool_family="mtk-brom",
        case_type="firmware_package",
        confidence=min(score + 0.1, 0.95),
        signals=signals,
    )
    profile.notes.append("MediaTek 固件包，建议使用 SP Flash Tool 或 BROM 模式刷写")
    return profile


def _detect_user_bundle(result: Any, inv: Any, rp: Any) -> Optional[CaseProfile]:
    """检测是否为用户自制简易包（少量分区 + 简单脚本）"""
    signals: List[str] = []
    score = 0.0

    total = getattr(result, 'total_steps', 0) or 0
    part_count = getattr(inv, 'partition_count', 0) or 0

    # 步骤少、分区少
    if 1 <= total <= 5 and 1 <= part_count <= 5:
        signals.append(f"步骤少({total})、分区少({part_count})")
        score += 0.30

    # 无固件
    fw = getattr(inv, 'firmware_files', []) or []
    if not fw:
        signals.append("不包含底层固件文件")
        score += 0.15

    # 无 android-info.txt
    if not (rp and getattr(rp, 'has_android_info', False)):
        score += 0.05

    # 无 payload
    if not (rp and getattr(rp, 'has_payload', False)):
        score += 0.05

    # 无 preloader
    if not (rp and getattr(rp, 'has_preloader', False)):
        score += 0.05

    # 类型为 fastboot
    if rp and getattr(rp, 'rom_flavor', '') == 'fastboot':
        signals.append("ROM 类型为 fastboot 刷机")
        score += 0.10

    if score < 0.5:
        return None

    profile = CaseProfile(
        vendor_family="generic_user",
        tool_family="fastboot-bat",
        case_type="user_bundle",
        confidence=min(score + 0.1, 0.95),
        signals=signals,
    )
    profile.notes.append("用户自制简易刷机包，不含底层固件，风险较低")
    return profile


# ============================================================
# 主入口
# ============================================================

def detect_case_profile(result: Any, inv: Any = None, rp: Any = None) -> CaseProfile:
    """
    分析刷机包案例特征。

    Args:
        result: HydraParseResult 实例
        inv: RomInventory 实例（可选，如 None 则从 result.rom_inv 取）
        rp: RomProfile 实例（可选，如 None 则从 result.rom_profile 取）

    Returns:
        CaseProfile
    """
    if inv is None:
        inv = getattr(result, 'rom_inv', None)
    if rp is None:
        rp = getattr(result, 'rom_profile', None)

    # 按置信度从高到低尝试各检测器
    detectors = [
        _detect_xiaomi,
        _detect_pixel,
        _detect_payload_ota,
        _detect_qcom_firmware,
        _detect_mtk_firmware,
        _detect_user_bundle,
    ]

    best: Optional[CaseProfile] = None
    for detect in detectors:
        cp = detect(result, inv, rp)
        if cp is not None and cp.confidence > 0.3:
            if best is None or cp.confidence > best.confidence:
                best = cp

    if best is not None:
        return best

    # 兜底：至少基于 RomProfile 给出通用分类
    if rp:
        flavor = getattr(rp, 'rom_flavor', 'unknown')
        platform = getattr(rp, 'platform', 'unknown')
        notes = []
        if flavor == 'payload':
            notes.append("通用 OTA payload 包")
        elif flavor == 'mtk-brom':
            notes.append("通用 MTK 固件包")
        elif flavor == 'fastboot':
            notes.append("通用 fastboot 刷机包")
        else:
            notes.append("未识别的刷机包类型")

        return CaseProfile(
            vendor_family="generic",
            tool_family=f"{flavor}-script" if flavor != 'unknown' else "unknown",
            case_type="unknown",
            confidence=0.3,
            signals=[],
            notes=notes,
        )

    return CaseProfile(
        vendor_family="unknown",
        tool_family="unknown",
        case_type="unknown",
        confidence=0.0,
        signals=[],
        notes=["无法识别刷机包类型"],
    )


__all__ = [
    "CaseProfile",
    "detect_case_profile",
]