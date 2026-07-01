# -*- coding: utf-8 -*-
# flash_tool/core/hydra/types.py
"""
Hydra — 数据类型定义
======================
独立的数据类，避免循环导入问题。
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict
import json

from .script_class import ClassMatchResult
from .rom_inventory import RomInventory


@dataclass
class HydraStep:
    """解析出的单步命令"""
    type: str                       # flash / erase / reboot / set_active / oem / getvar / devices / boot
    part: str = ""                  # 目标分区
    fileName: str = ""              # 镜像文件（flash 类型）
    params: str = ""                # 附加参数
    raw: str = ""                   # 原始命令文本
    risk: str = "B"                 # 风险等级 S/A/B/C
    condition: str = ""             # 条件（if 后的表达式）
    loop: str = ""                  # 所属循环原始文本
    call: str = ""                  # call 来源
    dynamic: bool = False           # 是否为动态生成（运行时才能确定）
    confidence: str = "certain"      # 步骤可信度: certain / estimated / placeholder / unknown
    line_no: int = 0                # 原始脚本行号
    note: str = ""                  # 步骤说明（例如 devices→检测设备连接）
    # 15C：步骤级标注
    source: str = "static"          # 步骤来源: static / tracer / sandbox / expander
    risk_subtype: str = ""          # 风险子类型: erase / critical_part / bootloader_part / slot / reboot / oem / check / flash_normal
    resource_note: str = ""         # 资源状态: "镜像文件存在" / "镜像文件缺失" / "无镜像依赖" / "需外部命令"


@dataclass
class HydraParseResult:
    """引擎解析的完整结果"""
    script_type: str                # "bat" | "sh" | "unknown"
    steps: List[HydraStep] = field(default_factory=list)
    is_simple: bool = True          # 是否可静态完全解析（旧架构兼容字段，真实值取 class_id）
    missing_files: List[str] = field(default_factory=list)
    variables: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    total_steps: int = 0
    dynamic_commands: int = 0
    has_delayed_expansion: bool = False
    summary: Dict[str, int] = field(default_factory=dict)  # 分类统计（由 build_summary 生成）
    placeholder_steps: int = 0          # 占位步骤数（confidence=placeholder）
    estimated_steps: int = 0            # 估计步骤数（confidence=estimated）
    recipe_match: ClassMatchResult = field(default_factory=ClassMatchResult)  # 脚本分类结果
    rom_inv: RomInventory = field(default_factory=RomInventory)                # ROM 资源清单
    rom_profile: Any = None  # RomProfile（懒加载，profile_rom 在 display_summary 首次访问时生成）
    script_resource_check: Any = None  # ScriptResourceCheckResult（懒加载）
    case_profile: Any = None  # CaseProfile（懒加载，detect_case_profile 在 display_summary 首次访问时生成）
    trace_engine: str = "bat_tracer"  # "bat_tracer" | "win_cmd_sandbox"
    notes: List[str] = field(default_factory=list)  # 风险/说明文本列表

    @property
    def execution_mode(self) -> Dict[str, Any]:
        """执行模式摘要"""
        return {
            "script_type": self.script_type,
            "trace_engine": self.trace_engine,
            "class_id": self.recipe_match.class_id if self.recipe_match.matched else None,
            "class_name": self.recipe_match.class_name if self.recipe_match.matched else None,
        }

    @property
    def confidence_summary(self) -> Dict[str, int]:
        """可信度统计"""
        certain = self.total_steps - self.placeholder_steps - self.estimated_steps
        return {
            "certain": max(0, certain),
            "estimated": self.estimated_steps,
            "placeholder": self.placeholder_steps,
            "has_uncertain_steps": (self.placeholder_steps + self.estimated_steps) > 0,
        }

    @property
    def risk_reasons(self) -> List[str]:
        """生成风险原因列表"""
        reasons = []
        critical = self.summary.get("critical_risk_steps", 0)
        high = self.summary.get("high_risk_steps", 0)
        has_wipe = self.summary.get("wipe_steps", 0) > 0
        has_unlock = self.summary.get("unlock_steps", 0) > 0
        has_vbmeta = any(
            s.part.lower() == "vbmeta" or "vbmeta" in (s.fileName or "").lower()
            for s in self.steps
        )
        has_super = any(
            s.part.lower() == "super" for s in self.steps
        )
        has_preloader = any(
            s.part.lower() in ("preloader", "lk", "tee", "tz", "sbl")
            for s in self.steps
        )

        if critical > 0:
            reasons.append(f"包含 {critical} 个高风险擦除/删除操作")
        if has_wipe:
            reasons.append("将擦除分区数据，请提前备份")
        if has_unlock:
            reasons.append("包含解锁操作，解锁后设备安全等级将降低")
        if has_vbmeta:
            reasons.append("将刷写 vbmeta 分区，可能影响 AVB 校验")
        if has_super:
            reasons.append("将刷写 super 分区，会重新影响 system/vendor/product")
        if has_preloader:
            reasons.append("⚠️ 将刷写 preloader/lk/tee 等底层分区，风险极高")
        if high > 20:
            reasons.append(f"大批量刷写操作（{high} 个），请确保刷机包与设备匹配")

        return reasons

    @property
    def resource_notes(self) -> List[str]:
        """资源相关说明"""
        notes_list = []
        if not self.rom_inv.rom_dir:
            return notes_list
        if self.rom_inv.has_payload_bin:
            notes_list.append("ROM 包含 payload.bin，将按已知分区列表估计展开")
        if self.rom_inv.has_image_zip:
            notes_list.append("ROM 包含 image-*.zip，匹配 Pixel fastboot update 食谱")
        if self.rom_inv.partition_count > 0:
            notes_list.append(f"ROM 中识别到 {self.rom_inv.partition_count} 个分区映像")
        missing = self.rom_inv.missing_images if hasattr(self.rom_inv, 'missing_images') else []
        if missing:
            notes_list.append(f"以下镜像文件未在 ROM 目录中找到: {', '.join(missing[:5])}")
        return notes_list

    @property
    def _rom_summary(self) -> Optional[Dict[str, Any]]:
        """ROM 包结构摘要（含 RomProfile + 完整性）"""
        if not self.rom_inv.rom_dir:
            return None
        # 懒加载 RomProfile
        if self.rom_profile is None:
            from .rom_profile import profile_rom
            self.rom_profile = profile_rom(self.rom_inv)
        p = self.rom_profile
        return {
            "image_count": self.rom_inv.image_count,
            "partition_count": self.rom_inv.partition_count,
            "has_images_dir": len(self.rom_inv.image_dirs) > 0,
            "has_payload_bin": self.rom_inv.has_payload_bin,
            "has_android_info": self.rom_inv.has_android_info,
            "has_image_zip": self.rom_inv.has_image_zip,
            # 18C+D：ROM Profile + 完整性
            "flavor": p.rom_flavor,
            "platform": p.platform,
            "slot_scheme": p.slot_scheme,
            "security_level": p.security_level,
            "mode_required": p.mode_required,
            "missing_critical": p.missing_critical,
            "integrity_notes": p.integrity_notes,
            "notes": p.notes,
        }

    @property
    def script_resource_summary(self) -> Optional[Dict[str, Any]]:
        """脚本-资源一致性校验摘要"""
        if not self.rom_inv.rom_dir:
            return None
        if self.script_resource_check is None:
            from .script_resource_checker import check_script_resources
            # 确保 rom_profile 已加载
            if self.rom_profile is None:
                from .rom_profile import profile_rom
                self.rom_profile = profile_rom(self.rom_inv)
            self.script_resource_check = check_script_resources(
                self.steps,
                self.rom_inv,
                self.rom_profile,
            )
        return self.script_resource_check.to_dict()

    @property
    def quality_summary(self) -> Optional[Dict[str, Any]]:
        """解析质量评分摘要"""
        from .quality_evaluator import evaluate_quality
        return evaluate_quality(self).to_dict()

    @property
    def case_profile_summary(self) -> Optional[Dict[str, Any]]:
        """刷机包案例特征摘要"""
        if self.case_profile is None:
            from .case_profile import detect_case_profile
            self.case_profile = detect_case_profile(
                self, self.rom_inv, self.rom_profile
            )
        return self.case_profile.to_dict()

    @property
    def display_summary(self) -> Dict[str, Any]:
        """标准化摘要，供前端直接消费"""
        risk_level = "unknown"
        critical = self.summary.get("critical_risk_steps", 0)
        high = self.summary.get("high_risk_steps", 0)
        if critical > 0:
            risk_level = "critical"
        elif high > 0:
            risk_level = "high"
        elif self.total_steps > 0:
            risk_level = "normal"

        summary = {
            "total": self.total_steps,
            "write": self.summary.get("write_steps", 0),
            "wipe": self.summary.get("wipe_steps", 0),
            "boot": self.summary.get("boot_steps", 0),
            "slot": self.summary.get("slot_steps", 0),
            "check": self.summary.get("check_steps", 0),
            "other": self.summary.get("other_steps", 0),
            "placeholder": self.placeholder_steps,
            "estimated": self.estimated_steps,
            "risk_level": risk_level,
            "has_uncertain_steps": (self.placeholder_steps + self.estimated_steps) > 0,
            "recipe": {
                "class": self.recipe_match.class_id,
                "name": self.recipe_match.class_name,
            } if self.recipe_match.matched else None,
            "rom": self._rom_summary,
            "trace_engine": self.trace_engine,
            # 15A+B：增强字段
            "execution_mode": self.execution_mode,
            "confidence": self.confidence_summary,
            "risk_reasons": self.risk_reasons,
            "resource_notes": self.resource_notes,
            "notes": self.notes,
            # 21：脚本-资源一致性校验
            "script_resource_check": self.script_resource_summary,
            # 22：解析质量评分
            "quality": self.quality_summary,
            # 23：刷机包案例特征
            "case_profile": self.case_profile_summary,
        }
        return summary

    @property
    def step_groups(self) -> Dict[str, list]:
        """步骤按分类分组，供前端折叠展示"""
        from .step_classifier import classify_step_type
        groups: Dict[str, list] = {
            "check": [],
            "wipe": [],
            "write": [],
            "slot": [],
            "boot": [],
            "other": [],
        }
        for s in self.steps:
            cat = classify_step_type(s.type)
            if cat not in groups:
                cat = "other"
            groups[cat].append(s)
        # 移除空组
        return {k: v for k, v in groups.items() if v}

    @property
    def risk_notes(self) -> List[str]:
        """自动生成风险提示文案"""
        notes = []
        summ = self.summary
        critical = summ.get("critical_risk_steps", 0)
        high = summ.get("high_risk_steps", 0)
        p = self.placeholder_steps
        e = self.estimated_steps

        if critical > 0:
            notes.append(f"该脚本包含 {critical} 个擦除/删除操作，风险较高，刷机前请确认数据已备份。")

        if high > 0:
            notes.append(f"该脚本包含 {high} 个写分区操作。")

        if p > 0:
            notes.append(f"该脚本包含 {p} 个通配符刷写步骤，实际刷写目标取决于目录中的镜像文件。")

        if e > 0:
            notes.append(f"该脚本包含 {e} 个估计步骤，可能因条件分支跳过。")

        if self.dynamic_commands > 0 and self.script_type == "bat":
            notes.append("部分命令依赖延迟展开变量，解析结果可能不完全准确。")

        if not notes:
            notes.append("该脚本均为确定步骤，无通配符或不确定操作。")

        return notes


__all__ = ["HydraStep", "HydraParseResult", "HydraOptions"]


@dataclass
class HydraOptions:
    """Hydra 引擎配置选项"""
    trace_mode: str = "auto"        # "auto" | "enabled" | "disabled" | "bat_only" | "sh_only"
    bat_tracer_enabled: bool = True
    sh_tracer_enabled: bool = True
    sh_tracer_timeout: int = 15     # SH tracer 超时秒数
    merge_threshold: float = 0.35   # 合并阈值：tracer步数 >= 静态步数 * 阈值 时直接使用
    auto_detect_type: bool = True   # 是否自动识别脚本类型
    verbose: bool = False           # 是否输出调试信息
    bat_trace_mode: str = "trace"   # BAT tracer 模式: "trace"(旧tracer) | "sandbox"(WinCmdSandbox) | "auto"(自动选择)

    def resolve(self, script_type: str) -> bool:
        """
        解析配置，判断指定脚本类型是否启用 tracer。

        返回 True 表示启用 tracer，False 表示仅用静态解析。
        """
        if self.trace_mode == "disabled":
            return False
        if self.trace_mode == "enabled":
            return True
        if self.trace_mode == "bat_only":
            return script_type == "bat"
        if self.trace_mode == "sh_only":
            return script_type == "sh"
        # auto 模式：按类型各自的启用开关
        if script_type == "bat":
            return self.bat_tracer_enabled
        if script_type == "sh":
            return self.sh_tracer_enabled
        return False

    def resolve_bat_trace_mode(self) -> str:
        """解析 BAT 追踪模式。"""
        return self.bat_trace_mode or "trace"