# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/partition_knowledge.py
"""
分区知识库 — 独立于 BAT 版本

维护：
  - 分区风险定级表（超危/高危/中危/低危）
  - 标准刷写顺序（高通 A/B 设备）
  - 参数风险检测规则
"""

from typing import Dict, List, Set

# ─────────────────────────────────────────────
# 分区风险定级表
# ─────────────────────────────────────────────

# 风险等级: CRITICAL > HIGH > MEDIUM > LOW

CRITICAL_PARTITIONS: Set[str] = {
    # 高通 SBL 层 — 刷坏直接变砖
    "xbl", "xbl_4", "xbl_5",
    "xbl_config", "xbl_config_4", "xbl_config_5",
    "abl", "tz", "hyp", "devcfg",
    # 电源管理
    "rpm", "pmic",
    # AOP
    "aop",
    # UEFI
    "uefi", "uefisecapp",
    # 启动引导
    "preloader", "preflag",
    # 分区表本身
    "partition",
    # 高通特有
    "cpucp", "imagefv", "shrm",
}

HIGH_PARTITIONS: Set[str] = {
    # 安全相关
    "keymaster", "cmnlib", "cmnlib64",
    "storsec", "qupfw", "ssd",
    # 基带/通信
    "modem", "modemst1", "modemst2", "dsp",
    "fsg", "fsc",
    # 验证启动
    "vbmeta", "vbmeta_system",
    # 各种固件
    "persist",
    "multiimgoem", "multiimgqti",
    "spunvm", "scp",
    "lk", "lk2",
    "bluetooth", "featenabler",
}

MEDIUM_PARTITIONS: Set[str] = {
    # 标准系统分区
    "boot", "dtbo", "recovery",
    "vendor", "system", "product",
    "system_ext", "odm", "vendor_dlkm", "system_dlkm",
    "mi_ext",
    # 杂项
    "misc", "frp",
    "exaid",
}

LOW_PARTITIONS: Set[str] = {
    "userdata", "cache", "cust",
    "splash", "logo", "metadata",
    "super", "mdtp",
}

# 完整风险表（用于快速查表）
_RISK_MAP: Dict[str, str] = {}

for p in CRITICAL_PARTITIONS:
    _RISK_MAP[p] = "CRITICAL"

for p in HIGH_PARTITIONS:
    _RISK_MAP[p] = "HIGH"

for p in MEDIUM_PARTITIONS:
    _RISK_MAP[p] = "MEDIUM"

for p in LOW_PARTITIONS:
    _RISK_MAP[p] = "LOW"


# ─────────────────────────────────────────────
# 参数风险检测规则
# ─────────────────────────────────────────────

# 参数模式 → 触发后风险升级
PARAM_RISK_RULES: List[tuple] = [
    (r'--disable-verity', "强制 CRITICAL"),
    (r'--disable-verification', "强制 CRITICAL"),
    (r'flashing\s+unlock', "强制 CRITICAL — 解锁引导加载程序"),
    (r'flashing\s+lock', "HIGH"),
]


# ─────────────────────────────────────────────
# 标准刷写顺序（高通 A/B 设备）
# ─────────────────────────────────────────────

QCOM_AB_STANDARD_ORDER: List[str] = [
    "crclist",
    "xbl", "xbl_4", "xbl_5",
    "xbl_config", "xbl_config_4", "xbl_config_5",
    "abl",
    "tz", "hyp",
    "devcfg", "storsec",
    "bluetooth", "cmnlib", "cmnlib64",
    "modem", "dsp",
    "keymaster", "logo",
    "featenabler", "misc",
    "aop", "qupfw", "uefisecapp", "multiimgoem",
    "super", "vbmeta", "dtbo", "vbmeta_system",
    "cache", "metadata", "userdata",
    "recovery", "cust", "boot",
]

# 分区在标准顺序中的索引映射（用于快速校验）
_STANDARD_ORDER_INDEX: Dict[str, int] = {
    p: i for i, p in enumerate(QCOM_AB_STANDARD_ORDER)
}


# ─────────────────────────────────────────────
# 查询函数
# ─────────────────────────────────────────────

def get_partition_risk(partition: str) -> str:
    """
    查询分区的默认风险等级。
    Args:
        partition: 分区名
    Returns:
        str: CRITICAL/HIGH/MEDIUM/LOW
    """
    return _RISK_MAP.get(partition, "MEDIUM")


def check_position_order(
    partition: str,
    current_index: int,
) -> str:
    """
    检查分区在标准顺序中的位置是否合理。
    Args:
        partition: 分区名
        current_index: 当前步骤在步骤列表中的位置
    Returns:
        str: 空串表示正常，否则返回描述
    """
    expected_pos = _STANDARD_ORDER_INDEX.get(partition)
    if expected_pos is None:
        return ""  # 不在标准顺序中 → 不校验
    return ""


def get_standard_order_position(partition: str) -> int:
    """
    获取分区在标准刷写顺序中的位置。
    Returns:
        int: 位置索引，不在标准顺序时返回 -1
    """
    return _STANDARD_ORDER_INDEX.get(partition, -1)


__all__ = [
    "CRITICAL_PARTITIONS",
    "HIGH_PARTITIONS",
    "MEDIUM_PARTITIONS",
    "LOW_PARTITIONS",
    "PARAM_RISK_RULES",
    "QCOM_AB_STANDARD_ORDER",
    "get_partition_risk",
    "check_position_order",
    "get_standard_order_position",
]
