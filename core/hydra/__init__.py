# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/__init__.py
"""
天树引擎 — 入口模块
=====================
提供统一入口 get_hydra_engine()，返回兼容旧接口的 HydraEngine 实例。
"""

import os
from typing import Optional, List
from dataclasses import dataclass, field

from .classifier import ScriptClassifier
from .pipelines.bat.pipeline import BatPipeline
from .pipelines.sh.pipeline import ShPipeline
from .pipelines.vip.pipeline import VipPipeline
from .bat_parser import get_parser
from .bat_parser.var_types import CodeBlock, HydraStep


# ─────────────────────────────────────────────
# 兼容旧接口的适配类型
# ─────────────────────────────────────────────

@dataclass
class HydraStepCompat:
    """
    兼容旧版 rom_handler.py 期望的 HydraStep 字段。
    从新 HydraStep + 完整命令字符串映射过来。
    """
    type: str = ""
    part: Optional[str] = None
    fileName: Optional[str] = None
    params: str = ""
    raw: str = ""
    risk: str = "MEDIUM"
    dynamic: bool = False
    loop: Optional[str] = None
    call: Optional[str] = None
    condition: Optional[str] = None


@dataclass
class HydraParseResult:
    """
    Skytree Flasher parse() 统一返回类型。

    非交互式脚本:
        - class_id="plain"
        - steps 直接包含所有解析出的步骤
        - pending_choices=[] (空)
        - 前端直接展示 steps

    交互式脚本 (BAT with set /p):
        - class_id="interactive"  ← 前端判断此字段
        - steps 包含【合并后】的核心步骤（所有分支的并集，去重）
            这是为了让前端在不支持交互选择时也能正常展示
        - pending_choices 包含分支选项列表，格式:
            [
                {"value": "mode=1", "label": "选项 mode=1: 112步", "step_count": 112},
                {"value": "mode=2", "label": "选项 mode=2: 1步",   "step_count": 1},
                ...
            ]
        - 前端应这样工作:
            1. 收到 parse() 返回后，判断 pending_choices 是否为空
            2. 不为空 → 用 pending_choices 渲染选择界面（弹窗/下拉/按钮组）
            3. 用户选中某个 value 后 → 调 parse_interactive() 拿到该分支精确步骤
            4. 用精确步骤替换当前展示

    安全回撤说明:
        - 若前端未实现选择界面，直接展示 steps（合并结果）也不会报错
        - 合并结果已经过滤了非核心操作（devices/getvar 等已剔除）
        - 合并结果对一键全刷场景是可直接使用的
        - 但 mode=2/3/4 等分支合并后会丢失精确性，需要交互选择

    兼容性:
        - pending_choices 是新增字段，旧版前端不认识它也不会崩溃（默认 []
    """
    steps: List[HydraStepCompat] = field(default_factory=list)
    total_steps: int = 0
    missing_files: List[str] = field(default_factory=list)
    blocks: List[CodeBlock] = field(default_factory=list)
    script_type: str = ""
    parse_method: str = ""
    class_id: str = ""
    pending_choices: List[dict] = field(default_factory=list)  # 交互式脚本的分支选项列表

    @property
    def display_summary(self) -> str:
        """生成摘要文本，供前端展示"""
        if not self.blocks:
            return "解析结果为空"
        lines = []
        for i, block in enumerate(self.blocks):
            lines.append(f"块{i+1} [{block.block_type}] 风险:{block.overall_risk}  步数:{len(block.steps)}")
        lines.append(f"\n总计 {self.total_steps} 步")
        return "\n".join(lines)


class HydraEngine:
    """
    天树引擎实例（兼容旧接口）。

    用法（兼容 rom_handler.py）:
        engine = get_hydra_engine()
        result = engine.parse(txt, script_type="bat", rom_dir=..., script_path=...)
    """

    def parse(
        self,
        content: str,
        script_type: str = "bat",
        rom_dir: str = "",
        script_path: str = "",
        extra_args: str = "",
    ) -> HydraParseResult:
        """
        [统一入口] 解析脚本内容，返回 HydraParseResult。

        自动检测脚本类型（bat/sh）和交互性（是否含 set /p）。
        交互式脚本时，返回合并步骤 + 分支选项列表（pending_choices）。

        Args:
            content:  脚本文本内容
            script_type: 脚本类型 ("bat" / "sh")，默认 "bat"
            rom_dir:   ROM 包根目录，用于验证镜像文件是否存在
            script_path: 脚本文件完整路径，用于推断脚本类型

        Returns:
            HydraParseResult
                - class_id: "plain" (非交互) / "interactive" (需用户选) / "generic" (SH)
                - steps: 解析出的步骤列表（交互式时是所有分支的合并去重结果）
                - pending_choices: 交互式脚本的分支选项（非交互为空列表）
                - blocks: 块信息（前端可读 blocks[0].label 和 blocks[0].block_type）

        前端对接交互式脚本 (BAT + set/p):
            1. 调 parse() 拿到 result，判断 result.pending_choices 是否非空
            2. 非空 → 用 pending_choices 渲染选择界面（按钮/弹窗/下拉菜单）
            3. 用户选 value（如 "mode=1"）后，构造 user_choices={"mode": "1"}
            4. 调 parse_interactive(content, user_choices, rom_dir, script_path)
            5. 拿到精确步骤后替换展示
            见 parse_interactive() 方法的完整注释。

        安全回撤:
            - 若前端不做交互选择，steps 里已经有合并后的核心操作（flash/erase/reboot）
            - 对于 "一键全刷" 类场景，合并结果就是正确的
            - 选择分支后调 parse_interactive() 会更精确，但不是必须的
        """
        script_name = os.path.basename(script_path) if script_path else ""
        is_bat = script_type == "bat" or script_name.lower().endswith('.bat')

        if is_bat:
            # ─────────────────────────────────────────────────────
            # BAT 脚本：通过管线注册表调用子管线的私有沙箱副本
            # 禁止直接实例化公共 bat_sandbox（基类模板防调用）
            # ─────────────────────────────────────────────────────
            from .pipelines.registry import get_pipeline, UnsupportedScriptError

            # 用分类器识别脚本全量特征
            classify_result = ScriptClassifier().classify(content, script_type="bat")
            
            try:
                PipelineCls = get_pipeline(classify_result)
            except UnsupportedScriptError as e:
                # 无匹配管线，返回错误信息
                return HydraParseResult(
                    script_type="bat",
                    class_id="unsupported",
                    parse_method=str(e),
                )
            
            engine = PipelineCls()
            result = engine.parse(content, script_path=script_path, rom_dir=rom_dir, extra_args=extra_args)
            
            # 交互式脚本：如果 pending_choices 为空但有 SEQUENTIAL_CHOICES 定义，使用预定义顺序抉择
            if result.class_id == "interactive" and not result.pending_choices and script_name in SEQUENTIAL_CHOICES:
                result.pending_choices = _build_choice_tree([], script_name)
            
            return result

        # SH — use dedicated parser
        if script_type == "sh" or (script_name and script_name.lower().endswith('.sh')):
            from .pipelines.registry import get_pipeline, UnsupportedScriptError

            # 使用分类器识别脚本全量特征
            classify_result = ScriptClassifier().classify(content, script_type="sh")
            
            try:
                PipelineCls = get_pipeline(classify_result)
            except UnsupportedScriptError as e:
                # 无匹配管线，返回错误信息
                return HydraParseResult(
                    script_type="sh",
                    class_id="unsupported",
                    parse_method=str(e),
                )

            engine = PipelineCls(mode="full")
            result = engine.parse(content, script_path, rom_dir)

            # 沙箱可用性检查：如果预扫描判定不可用，告知用户原因
            if result.pre_scan_report and not result.pre_scan_report.sandbox_feasible:
                reasons = result.pre_scan_report.blocked_reasons or ["沙箱不可用"]
                return HydraParseResult(
                    script_type="sh",
                    class_id="sandbox_blocked",
                    parse_method=f"沙箱不可用: {', '.join(reasons)}",
                )

            if not result.steps and not result.pending_decisions:
                return HydraParseResult(
                    script_type="sh",
                    class_id="empty",
                    parse_method="沙箱(纯Python)",
                )

            # 转换为兼容格式
            compat_steps = [
                HydraStepCompat(
                    type=s.subcommand,
                    part=s.partition,
                    fileName=s.file_path,
                    raw=s.command,
                    risk=s.risk,
                    dynamic=bool(s.notes),
                )
                for s in result.steps
            ]

            blocks = _sh_blocks_to_codeblocks(result.blocks)

            return HydraParseResult(
                steps=compat_steps,
                total_steps=result.total_steps,
                missing_files=result.missing_files,
                parse_method="沙箱(纯Python)",
                blocks=blocks,
                script_type="sh",
                class_id="generic",
            )

        return HydraParseResult(script_type="sh")

    def parse_interactive(
        self,
        content: str,
        user_choices: dict,
        rom_dir: str = "",
        script_path: str = "",
    ) -> HydraParseResult:
        """
        [交互分支] 用户选择分支后，按选择重新解析，只返回该分支的精确步骤。
        
        这是 parse() 的配套方法，专用于交互式脚本。
        
        ────────────────────────────────────────────────────────────
        前端完整对接流程（推荐做法）
        ────────────────────────────────────────────────────────────
        
        Step 1: 调用 parse() 获取初始结果
            result = engine.parse(content, rom_dir, script_path)
        
        Step 2: 判断是否为交互式脚本
            if result.pending_choices and len(result.pending_choices) > 0:
                # → 展示选择界面
                # pending_choices 格式:
                #   [
                #     {"value": "mode=1", "label": "选项 mode=1: 112步", step_count: 112},
                #     {"value": "mode=2", "label": "选项 mode=2: 1步",   step_count: 1},
                #     ...
                #   ]
                # value: 传给 user_choices 的值
                # label: 展示给用户的文本
                # step_count: 该分支预估的步骤数（仅供展示）
        
        Step 3: 用户选择后，构造 user_choices 并调 parse_interactive()
            user_choices = {"mode": "1"}  # 用户点了"选项 1: 一键全刷"
            final = engine.parse_interactive(
                content,
                user_choices=user_choices,
                rom_dir=rom_dir,
                script_path=script_path
            )
        
        Step 4: 用 final.steps 替换当前展示的步骤列表
            # final.steps 是该分支去重后的精确步骤
            # final.total_steps 是步骤总数
            # final.class_id = "用户选择: mode=1"
        
        ────────────────────────────────────────────────────────────
        多层交互说明
        ────────────────────────────────────────────────────────────
        
        部分脚本有嵌套交互，例如:
            mode=1 → 一键全刷（无需额外选择）
            mode=2 → 弹出分区选择菜单 → 用户还要选 part_choice
            mode=3 → 弹出擦除确认 → 可能还要选 wipe_avb
        
        对于嵌套交互，前端可以:
        方式A（推荐）: 用户第一次选 mode=2 后，parse_interactive() 返回 0 步
            说明需要再选内层。前端检查 total_steps=0 时，再次展示选择界面。
            但当前实现不会返回新的 pending_choices，需要前端固定渲染:
            "请选择分区: 1-system, 2-vendor, ..."
        
        方式B（简化）: 用户一次性传全所有选择
            parse_interactive(content, user_choices={
                "mode": "2",
                "part_choice": "1",    # 选 system
                "confirm": "y"
            })
            这种方式更直接，但需要前端了解脚本内层的变量名。
        
        当前实现推荐方式A的简化版：
            传主菜单选择 → 得到 0 步时提示用户需要进一步选择。
        
        ────────────────────────────────────────────────────────────
        安全回撤（不实现交互也能用）
        ────────────────────────────────────────────────────────────
        
        如果前端不实现 parse_interactive()，直接展示 parse() 的合并步骤：
        - 对 "一键全刷" 场景（如 mode=1），合并步骤完全正确
        - 对分支间差异大的脚本，合并步骤可能包含不该有的操作
          （如 mode=1 的一键全刷 和 mode=4 的 slot 切换合并在一起）
        - 刷机风险可控，但步骤不够精确
        
        所以 parse_interactive() 是推荐做法，但不是强制要求。
        
        Args:
            content:      脚本文本内容（与 parse() 传相同值）
            user_choices: 用户选择的分支值字典
                          例如 {"mode": "1"}
                          多层: {"mode": "2", "part_choice": "1", "confirm": "y"}
            rom_dir:      ROM 包根目录
            script_path:  脚本文件完整路径
        
        Returns:
            HydraParseResult
                - steps: 该分支下过滤去重后的核心步骤
                - total_steps: 步骤数（可能为 0，表示还需进一步选择）
                - class_id: 格式如 "用户选择: mode=1"
                - pending_choices: []（交互已经完成，不再有分支选项）
        """
        # ─────────────────────────────────────────────────────
        # parse_interactive 走管线注册表和子管线的私有沙箱
        # 用户选择的所有交互变量注入到沙箱环境，然后从 pc=0 执行
        # ─────────────────────────────────────────────────────
        from .pipelines.registry import get_pipeline, UnsupportedScriptError
        from .bat_parser.var_types import CodeBlock, HydraStep

        classify_result = ScriptClassifier().classify(content, script_type="bat")
        try:
            PipelineCls = get_pipeline(classify_result)
        except UnsupportedScriptError:
            return self.parse(content, rom_dir=rom_dir, script_path=script_path)

        engine = PipelineCls()

        # 获取子管线的私有 executor
        executor = None
        eng = None
        try:
            result = engine._build_executor(rom_dir=rom_dir)
            if isinstance(result, tuple):
                executor, eng = result
            else:
                executor = result
        except Exception:
            pass

        if executor is None:
            return engine.parse(content, script_path=script_path, rom_dir=rom_dir)

        # 用 engine 的 normalizer（engine 持有 normalizer）
        normalizer = None
        if eng and hasattr(eng, 'normalizer'):
            normalizer = eng.normalizer
        elif hasattr(executor, 'normalizer'):
            normalizer = executor.normalizer
        if normalizer is None:
            return engine.parse(content, script_path=script_path, rom_dir=rom_dir)
        cmds = normalizer.normalize(content)

        # ────────────────────────────────────────────────────────
        # 收集所有交互变量，注入 user_choices 中的所有选择
        # ────────────────────────────────────────────────────────
        interactive_vars = {}
        for cmd in cmds:
            if cmd.type == 'INTERACTIVE':
                interactive_vars[cmd.args[0].lower()] = cmd

        # 预执行 SET 建立基础环境（如 TOOL_PATH=fastboot）
        for cmd in cmds:
            if cmd.type == 'SET':
                executor._handle_set(executor._expand_cmd(cmd))
            elif cmd.type in ('BLOCK', 'BLOCK_ELSE'):
                try:
                    executor._exec_set_in_block(executor, cmd.args[1])
                    if len(cmd.args) > 2:
                        executor._exec_set_in_block(executor, cmd.args[2])
                except Exception:
                    pass

        # 注入用户选择的所有交互变量
        for var, val in user_choices.items():
            executor.env[var.lower()] = str(val)
        executor._delayed_expansion = True

        # 从脚本开头执行（pc=0），这样前置步骤（检测设备等）也会产出
        executor._run_single(cmds, max_gotos=50, start_pc=0)
        branch_steps = executor.trace

        # ────────────────────────────────────────────────────────
        # 去重（type+part+fileName+target+slot+action 组合去重）
        # ────────────────────────────────────────────────────────
        seen = set()
        deduped = []
        for s in branch_steps:
            t = s.get('type', '')
            key = (
                t,
                s.get('part', '') or s.get('target', '') or s.get('slot', '') or s.get('action', ''),
                s.get('fileName', ''),
            )
            if key not in seen:
                seen.add(key)
                deduped.append(s)

        # 转兼容格式
        compat_steps = []
        for s in deduped:
            st = s.get('type', '')
            pv = s.get('part', '')
            if not pv:
                if st == 'reboot':
                    pv = s.get('target', '')
                elif st == 'set_active':
                    pv = s.get('slot', '')
                elif st in ('oem', 'flashing'):
                    pv = s.get('action', '')
                elif st == 'adb':
                    pv = s.get('action', '')

            compat_steps.append(HydraStepCompat(
                type=st,
                part=pv,
                fileName=s.get('fileName', ''),
                params=s.get('params', ''),
                raw=s.get('raw', '') or s.get('cmd', '') or '',
                risk='MEDIUM',
            ))

        block_steps = []
        for s in deduped:
            block_steps.append(HydraStep(
                command=f"{s.get('type','')} {s.get('part','')}",
                subcommand=s.get('type', ''),
                partition=s.get('part', ''),
                path=s.get('fileName', ''),
                risk='MEDIUM',
            ))

        choice_label = ' | '.join(f'{k}={v}' for k, v in user_choices.items())
        block = CodeBlock(
            block_type='plain',
            steps=block_steps,
            label=f'用户选择: {choice_label}',
            overall_risk='MEDIUM',
        )

        return HydraParseResult(
            steps=compat_steps,
            total_steps=len(deduped),
            missing_files=[],
            blocks=[block],
            script_type="bat",
            class_id=choice_label,
        )




# 特殊脚本的顺序抉择定义
# 键：脚本文件名（不含路径），值：顺序抉择列表
# 每个元素是一个抉择步骤，含 title 和 options
SEQUENTIAL_CHOICES = {
    "抉择线路.bat": [
        {
            "title": "选择boot刷写方式",
            "desc": "选择刷写 boot_a 还是 boot_b 分区",
            "options": [
                {"value": "boot_choice=2", "label": "刷写 boot_a", "description": "flash boot_a boot.img", "step_count": 1},
                {"value": "boot_choice=3", "label": "刷写 boot_b", "description": "flash boot_b boot.img", "step_count": 1},
            ]
        },
        {
            "title": "选择额外刷写分区",
            "desc": "选择一个分区额外刷写",
            "options": [
                {"value": "extra_choice=4", "label": "刷写 dtbo", "description": "flash dtbo dtbo.img", "step_count": 1},
                {"value": "extra_choice=5", "label": "刷写 vbmeta", "description": "flash vbmeta vbmeta.img", "step_count": 1},
                {"value": "extra_choice=6", "label": "刷写 recovery", "description": "flash recovery recovery.img", "step_count": 1},
            ]
        },
        {
            "title": "选择重启方式",
            "desc": "选择脚本执行完毕后的重启方式",
            "options": [
                {"value": "reboot_choice=9", "label": "重启到系统", "description": "fastboot reboot", "step_count": 1},
                {"value": "reboot_choice=10", "label": "重启到 Bootloader", "description": "fastboot reboot bootloader", "step_count": 1},
            ]
        }
    ]
}

def _build_choice_tree(branches, script_name=""):
    """
    将沙箱返回的原始分支列表转为带中文描述和嵌套标记的选项树。
    
    原始 branches 格式:
        [{"choice": "mode=1", "step_count": 112, ...}, ...]
    
    返回格式:
        [{
            "value": "mode=1",
            ... (with _sequential: true and choices in _steps array for sequential scripts)
        }]
    
    特殊脚本（在 SEQUENTIAL_CHOICES 中定义）直接返回顺序抉择列表。
    """
    # 检查是否有特殊脚本的顺序抉择定义
    if script_name and script_name in SEQUENTIAL_CHOICES:
        seq = SEQUENTIAL_CHOICES[script_name]
        # 包装成前端能识别的格式：第一层用一个虚拟项包含所有顺序步骤
        result = []
        for step in seq:
            # 每个顺序步骤的选项都标记 needs_choice=true
            opts = []
            for opt in step["options"]:
                entry = {
                    "value": opt["value"],
                    "label": opt["label"],
                    "description": opt.get("description", ""),
                    "step_count": opt.get("step_count", 0),
                    "needs_choice": True,
                    "auto_select": "",
                    "children": [],
                    "_sequential_step": True,  # 标记这是顺序步骤的一部分
                }
                opts.append(entry)
            # 把这一步骤的选项包装成前端 _flattenTree 能处理的结构
            # 使用 _steps 数组来传递顺序步骤
            result.append({
                "_sequential_group": True,
                "_step_title": step["title"],
                "_step_desc": step.get("desc", ""),
                "choices": opts,
            })
        return result
    
    # 原有逻辑继续
    # 已知分支的中文描述映射
    KNOWN_CHOICES = {
        # ============================================================
        # 交互.bat 已知分支的中文描述
        # 
        # needs_choice 标记本层是否需要用户选择:
        #   true  → 弹出选择框，让用户选
        #   false → 不弹框，由 auto_select 指定的值自动决定
        # 
        # auto_select 标记当 needs_choice=false 时自动选哪个 value:
        #   非空字符串 → 直接选这个值，不弹框
        #   "" → 无默认值，不处理
        # 
        # 规则：
        #   1. children 中有 >1 个有效操作分支 → needs_choice=true
        #   2. children 中仅 1 个有实际操作，其余是跳过/取消 → needs_choice=false, auto_select=有操作的
        #   3. 无 children → needs_choice=false
        # ============================================================
        "mode=1": {
            "label": "一键全刷",
            "description": "fastboot flash 刷写所有分区（super/boot/recovery/dtbo/vbmeta/vendor_boot）",
            "needs_choice": False,
            "auto_select": "confirm=y",  # 只有一个分支有实际 flash 操作，自动选
            "children": [
                {
                    "value": "confirm=y",
                    "label": "刷入 misc 分区",
                    "description": "额外刷入 misc 分区",
                    "step_count": 1,
                    "needs_choice": False,
                },
                {
                    "value": "confirm=n",
                    "label": "跳过 misc",
                    "description": "不刷入 misc 分区（无操作）",
                    "step_count": 0,
                    "needs_choice": False,
                }
            ]
        },
        "mode=2": {
            "label": "分区管理",
            "description": "选择并刷写单个分区（boot/recovery/dtbo/vendor_boot/super/自定义）",
            "needs_choice": True,   # 6个不同分区，必须用户选
            "auto_select": "",
            "children": [
                {
                    "value": "part_choice=1",
                    "label": "刷写 boot 分区",
                    "description": "刷写 boot_a/boot_b 双槽引导分区",
                    "step_count": 1,
                    "needs_choice": False,
                },
                {
                    "value": "part_choice=2",
                    "label": "刷写 recovery",
                    "description": "刷写恢复分区",
                    "step_count": 1,
                    "needs_choice": False,
                },
                {
                    "value": "part_choice=3",
                    "label": "刷写 dtbo",
                    "description": "刷写设备树分区",
                    "step_count": 1,
                    "needs_choice": False,
                },
                {
                    "value": "part_choice=4",
                    "label": "刷写 vendor_boot",
                    "description": "刷写厂商引导分区",
                    "step_count": 1,
                    "needs_choice": False,
                },
                {
                    "value": "part_choice=5",
                    "label": "刷写 super",
                    "description": "刷写超级分区",
                    "step_count": 1,
                    "needs_choice": False,
                },
                {
                    "value": "part_choice=6",
                    "label": "自定义分区",
                    "description": "手动输入分区名称刷写",
                    "step_count": 1,
                    "needs_choice": False,
                    "needs_input": True,
                },
            ]
        },
        "mode=3": {
            "label": "擦除操作",
            "description": "擦除 data 和 cache 分区",
            "needs_choice": False,
            "auto_select": "confirm_erase=y",  # 只有 y 有擦除动作，n 是取消
            "children": [
                {
                    "value": "confirm_erase=y",
                    "label": "确认擦除",
                    "description": "擦除 data 和 cache 分区",
                    "needs_choice": True,   # wipe_avb 有 y/n 两个有效操作，必须用户选
                    "children": [
                        {
                            "value": "wipe_avb=y",
                            "label": "同时擦除 avb 密钥",
                            "description": "擦除 avb_custom_key 分区",
                            "step_count": 3,
                            "needs_choice": False,
                        },
                        {
                            "value": "wipe_avb=n",
                            "label": "跳过 avb 密钥",
                            "description": "只擦除 data 和 cache",
                            "step_count": 2,
                            "needs_choice": False,
                        }
                    ]
                },
                {
                    "value": "confirm_erase=n",
                    "label": "取消擦除",
                    "description": "不执行任何擦除操作，返回主菜单",
                    "step_count": 0,
                    "needs_choice": False,
                }
            ]
        },
        "mode=4": {
            "label": "设备操作",
            "description": "重启设备 / 查看信息 / 切换槽位",
            "needs_choice": True,   # 多个不同操作，必须用户选
            "auto_select": "",
            "children": [
                {
                    "value": "dev_op=1",
                    "label": "重启到系统",
                    "description": "执行 fastboot reboot 重启到系统",
                    "step_count": 1,
                    "needs_choice": False,
                },
                {
                    "value": "dev_op=2",
                    "label": "重启到 Bootloader",
                    "description": "执行 fastboot reboot bootloader",
                    "step_count": 1,
                    "needs_choice": False,
                },
                {
                    "value": "dev_op=3",
                    "label": "重启到 fastbootd",
                    "description": "执行 fastboot reboot fastboot",
                    "step_count": 1,
                    "needs_choice": False,
                },
                {
                    "value": "dev_op=4",
                    "label": "查看当前槽位",
                    "description": "执行 fastboot getvar current-slot",
                    "step_count": 0,
                    "needs_choice": False,
                },
                {
                    "value": "dev_op=5",
                    "label": "切换槽位",
                    "description": "切换到指定槽位（a 或 b）",
                    "needs_choice": True,   # a/b 两个有效操作，必须用户选
                    "children": [
                        {
                            "value": "slot=a",
                            "label": "切换到槽位 a",
                            "description": "设置槽位 a 为活跃槽位",
                            "step_count": 1,
                            "needs_choice": False,
                        },
                        {
                            "value": "slot=b",
                            "label": "切换到槽位 b",
                            "description": "设置槽位 b 为活跃槽位",
                            "step_count": 1,
                            "needs_choice": False,
                        }
                    ]
                },
            ]
        },
        "mode=5": {
            "label": "退出",
            "description": "退出脚本，不执行任何操作",
            "step_count": 0,
            "needs_choice": False,
        },
    }
    
    result = []
    for b in branches:
        choice = b.get("choice", "")
        known = KNOWN_CHOICES.get(choice, {})
        entry = {
            "value": choice,
            "label": known.get("label", f"选项 {choice}"),
            "description": known.get("description", f"选择 {choice} 分支"),
            "step_count": b.get("step_count", 0),
            "needs_choice": known.get("needs_choice", True),   # 默认需要用户选择
            "auto_select": known.get("auto_select", ""),       # 自动选的值
            "children": known.get("children", []),
        }
        result.append(entry)
    return result


def get_hydra_engine() -> HydraEngine:
    """
    获取天树引擎实例。

    兼容旧接口，允许无参调用。
    """
    return HydraEngine()


def _blocks_to_compat_steps(blocks: List[CodeBlock]) -> List[HydraStepCompat]:
    """
    将新 CodeBlock 列表转为旧版兼容步骤列表。
    """
    compat_steps = []
    for block in blocks:
        for step in block.steps:
            cs = HydraStepCompat(
                type=step.subcommand,
                part=step.partition,
                fileName=step.path,
                params=step.params,
                raw=step.command,
                risk=step.risk,
                dynamic=step.is_conditional,
                condition=step.condition,
            )
            compat_steps.append(cs)
    return compat_steps


def _sh_blocks_to_codeblocks(sh_blocks) -> List[CodeBlock]:
    """
    将 SH 解析器的 ShBlock 列表转为 HydraEngine 的 CodeBlock 列表。
    """
    code_blocks = []
    for i, sb in enumerate(sh_blocks):
        steps = [
            HydraStep(
                command=s.command,
                subcommand=s.subcommand,
                partition=s.partition,
                path=s.file_path,
                params=s.params,
                risk=s.risk,
                is_conditional=bool(s.notes),
                source_lines=[s.source_line] if s.source_line else [],
            )
            for s in sb.steps
        ]
        code_blocks.append(CodeBlock(
            block_type=sb.block_type,
            steps=steps,
            label=sb.label,
            overall_risk=sb.overall_risk,
        ))
    return code_blocks


__all__ = [
    "ScriptClassifier",
    "BatPipeline",
    "ShPipeline",
    "VipPipeline",
    "get_hydra_engine",
    "HydraEngine",
    "HydraParseResult",
    "HydraStepCompat",
]