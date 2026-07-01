# -*- coding: utf-8 -*-
# flash_tool/core/hydra/__init__.py
"""
天树引擎 — 入口模块
=====================
架构：脚本分类器 → 解析管线。

- 分类器（classifier.py）：分析步骤结构特征，输出 class_id
- 解析管线：根据 class_id 执行对应的解析策略
- 可扩展：class_id 不固定，新增脚本类型时加分类规则 + 解析方法
"""

from .ast_parser import ASTParser
from .symbol_table import SymbolTable
from .environment import Environment
from .command_extractor import CommandExtractor
from .execution_tracer import ExecutionTracer
from .bat_execution_tracer import BatExecutionTracer
from .types import HydraStep, HydraParseResult, HydraOptions
from .step_classifier import build_summary, annotate_confidence, count_placeholder_steps, count_estimated_steps, annotate_all_steps
from .classifier import ScriptClassifier
from .rom_inventory import scan_rom
from .expander import expand_steps

from typing import List, Optional
import re
import os


class Engine:
    """
    解析引擎主类。
    分类器 + 解析管线。
    """

    def __init__(self, options: Optional["HydraOptions"] = None):
        self.options = options or HydraOptions()
        self.ast_parser = ASTParser()
        self.symbol_table = SymbolTable()
        self.environment = Environment(symbol_table=self.symbol_table)
        self.command_extractor = CommandExtractor()
        self.execution_tracer = ExecutionTracer()
        self.bat_execution_tracer = BatExecutionTracer()
        self.classifier = ScriptClassifier()

    def parse(
        self,
        content: str,
        script_type: str = "auto",
        rom_dir: str = "",
        script_path: str = "",
    ) -> HydraParseResult:
        """
        解析脚本，返回结构化结果。

        Args:
            content: 脚本字符串内容
            script_type: "bat" | "sh" | "auto"
            rom_dir: ROM 包根目录
            script_path: 脚本文件路径

        Returns:
            HydraParseResult
        """
        # 预处理
        from .script_preprocessor import preprocess_script
        content = preprocess_script(content, script_type=script_type)
        from .script_type_detector import detect_script_type
        filename = os.path.basename(script_path) if script_path else ""
        if not script_type or script_type == "auto":
            detected = detect_script_type(content, filename)
            if detected != "unknown":
                script_type = detected

        # Step 1：分类
        class_result = self.classifier.classify(content=content)
        class_id = class_result.class_id

        # ROM 扫描
        rom_inv = scan_rom(rom_dir)

        # Step 2：按分类执行对应解析管线
        steps = []
        env_result = None
        warnings = []

        # 组装完整 key（父类/子类）
        pipeline_key = f"{script_type}/{class_id}"

        # 解析管线映射表 — 可扩展，新增 class_id 时在此添加
        # key 格式优先匹配 "{父类}/{子类}"，再 fallback 到纯子类
        pipeline_map = {
            # bat 类
            "bat/linear": self._parse_linear,
            "bat/conditional": self._parse_conditional,
            "bat/function": self._parse_function,
            "bat/payload": self._parse_payload,
            "bat/legacy": self._parse_legacy,
            # sh 类
            "sh/linear": self._parse_linear,
            "sh/conditional": self._parse_conditional,
            "sh/function": self._parse_sh_function_shell,
            "sh/payload": self._parse_payload,
            "sh/legacy": self._parse_legacy,
            # 通用 fallback（无父类前缀时）
            "linear": self._parse_linear,
            "conditional": self._parse_conditional,
            "function": self._parse_function,
            "payload": self._parse_payload,
            "legacy": self._parse_legacy,
        }

        parser = pipeline_map.get(pipeline_key) or pipeline_map.get(class_id, self._parse_legacy)
        steps, env_result = parser(content, script_type, rom_dir, script_path)

        # 展开器
        expander_steps = expand_steps(class_id, rom_inv)
        if expander_steps:
            seen = {self._step_semantic_key(s) for s in steps}
            for s in expander_steps:
                key = self._step_semantic_key(s)
                if key not in seen:
                    seen.add(key)
                    steps.append(s)

        # 标注
        annotate_confidence(steps)
        annotate_all_steps(
            steps,
            rom_inv=rom_inv,
            rom_dir=rom_dir,
            expander_count=len(expander_steps) if expander_steps else 0,
            script_dir=os.path.dirname(os.path.abspath(script_path)) if script_path else "",
            script_path=script_path,
            script_type=script_type,
        )

        result = HydraParseResult(
            script_type=script_type,
            steps=steps,
            is_simple=(class_id in ("linear", "legacy")),
            missing_files=env_result.missing_files if env_result else [],
            variables=dict(self.symbol_table.get_all()),
            warnings=warnings,
            total_steps=len(steps),
            dynamic_commands=env_result.dynamic_commands if env_result else 0,
            has_delayed_expansion=env_result.has_delayed_expansion if env_result else False,
            summary=build_summary(steps),
            placeholder_steps=count_placeholder_steps(steps),
            estimated_steps=count_estimated_steps(steps),
            recipe_match=class_result,
            rom_inv=rom_inv,
        )

        return result

    # ================================================================
    # 解析管线
    # ================================================================

    def _parse_linear(self, content, script_type, rom_dir, script_path):
        """linear：AST + 环境模拟 + extractor"""
        ast_result = self.ast_parser.parse(content, script_type=script_type, script_path=script_path)
        if ast_result is None:
            return [], None
        env_result = self.environment.simulate(
            ast=ast_result, content=content,
            script_type=script_type, rom_dir=rom_dir, script_path=script_path,
        )
        steps = self.command_extractor.extract(env_result=env_result, rom_dir=rom_dir)
        # 私有去重
        steps = self._dedup_simple(steps)
        return steps, env_result

    def _dedup_simple(self, steps):
        """简单去重：每个 (type, part) 最多保留 2 次（metadata/bootloader 擦除或重启）。"""
        seen = {}
        result = []
        multi_allowed = {("erase", "metadata"): 2, ("reboot", "bootloader"): 2}
        for s in steps:
            key = (s.type.strip().lower() if s.type else "",
                   s.part.strip().lower() if s.part else "")
            max_count = multi_allowed.get(key, 1)
            current = seen.get(key, 0)
            if current < max_count:
                seen[key] = current + 1
                result.append(s)
        return result

    def _parse_conditional(self, content, script_type, rom_dir, script_path):
        """conditional：AST + 环境模拟 + extractor + tracer"""
        ast_result = self.ast_parser.parse(content, script_type=script_type, script_path=script_path)
        if ast_result is None:
            return [], None
        env_result = self.environment.simulate(
            ast=ast_result, content=content,
            script_type=script_type, rom_dir=rom_dir, script_path=script_path,
        )
        steps = self.command_extractor.extract(env_result=env_result, rom_dir=rom_dir)

        tracer_steps = self._run_tracer(content, script_type, rom_dir, script_path)
        if tracer_steps:
            steps = self._merge_tracer_steps_conditional(steps, tracer_steps)
        # 私有去重
        steps = self._dedup_simple(steps)
        return steps, env_result

    def _merge_tracer_steps_conditional(self, static_steps, tracer_steps):
        """conditional 管线私有：合并静态步骤和 tracer 步骤（去重，按行号排序）。"""
        seen = {self._step_semantic_key(s) for s in static_steps}
        # 额外宽松去重：通配符步骤（part 含 *）仅比较 type + 通配符后缀
        wildcard_seen = set()
        for s in static_steps:
            p = s.part.strip().lower() if s.part else ""
            if '*' in p:
                suffix = re.sub(r'^.*?\*', '', p)
                wildcard_seen.add((s.type.strip().lower() if s.type else "", suffix))
        for s in tracer_steps:
            key = self._step_semantic_key(s)
            if key in seen:
                continue
            p = s.part.strip().lower() if s.part else ""
            if '*' in p:
                suffix = re.sub(r'^.*?\*', '', p)
                wc_key = (s.type.strip().lower() if s.type else "", suffix)
                if wc_key in wildcard_seen:
                    continue
                wildcard_seen.add(wc_key)
            seen.add(key)
            static_steps.append(s)
        static_steps.sort(key=lambda x: x.line_no if x.line_no else 9999)
        return static_steps

    def _parse_function(self, content, script_type, rom_dir, script_path):
        """function：AST + 环境模拟 + extractor（函数由环境模拟展开）"""
        ast_result = self.ast_parser.parse(content, script_type=script_type, script_path=script_path)
        if ast_result is None:
            return [], None
        env_result = self.environment.simulate(
            ast=ast_result, content=content,
            script_type=script_type, rom_dir=rom_dir, script_path=script_path,
        )
        steps = self.command_extractor.extract(env_result=env_result, rom_dir=rom_dir)
        # 私有去重
        steps = self._dedup_simple(steps)
        return steps, env_result

    def _parse_payload(self, content, script_type, rom_dir, script_path):
        """payload：返回空列表，由 expander 补充"""
        return [], None

    def _parse_sh_function_shell(self, content, script_type, rom_dir, script_path):
        """
        sh/function_shell：SH 函数脚本专用解析管线。
        
        从脚本原文中用正则提取 fastboot 命令行，清理后直接构造 HydraStep。
        
        增强能力：
        - 解析脚本中的静态列表变量（如 PARTITION_LIST_DEFAULT）
        - 展开 for 循环，为每个分区生成具体的 flash 步骤
        
        不依赖环境模拟——函数体内的 if/while 等控制结构在环境模拟重解析时，
        内部的 fastboot 命令因条件评估被跳过。
        """
        import re
        
        lines = content.split('\n')
        
        # ============================================================
        # 第1步：提取脚本顶层的静态变量赋值（取第一次赋值）
        # ============================================================
        var_assignments = {}  # 变量名 -> 值（字符串）
        in_function = False
        function_bodies = {}  # 函数名 -> [(line_no, line_text)]
        current_func = None
        func_lines = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # 检测函数定义开始：func_name() { 或 function func_name
            func_match = re.match(r'^([a-zA-Z_]\w*)\s*\(\s*\)\s*\{?\s*$', stripped)
            func_match2 = re.match(r'^function\s+([a-zA-Z_]\w*)\s*\{?\s*$', stripped)
            if func_match or func_match2:
                in_function = True
                current_func = (func_match or func_match2).group(1)
                func_lines = []
                continue
            
            # 检测函数结束
            if in_function and (stripped == '}' or stripped == '};'):
                function_bodies[current_func] = func_lines
                in_function = False
                current_func = None
                continue
            
            if in_function:
                func_lines.append((i + 1, line))
                continue
            
            # 不在函数体内 → 提取赋值
            if stripped.startswith('#'):
                continue
            
            # VAR=$OTHER_VAR（带双引号）- 必须在纯字符串之前，否则 $VAR 会被当作普通字符串
            m = re.match(r'^([A-Z_]\w*)\s*=\s*"\$(\w+)"\s*$', stripped)
            if m and m.group(1) not in var_assignments:
                var_assignments[m.group(1)] = f"${{{m.group(2)}}}"
                continue
            m = re.match(r'^([A-Z_]\w*)\s*=\s*\$(\w+)\s*$', stripped)
            if m and m.group(1) not in var_assignments:
                var_assignments[m.group(1)] = f"${{{m.group(2)}}}"
                continue
            # VAR="value" 或 VAR='value'
            m = re.match(r'^([A-Z_]\w*)\s*=\s*"([^"]*)"\s*$', stripped)
            if m and m.group(1) not in var_assignments:
                var_assignments[m.group(1)] = m.group(2)
                continue
            m = re.match(r"^([A-Z_]\w*)\s*=\s*'([^']*)'\s*$", stripped)
            if m and m.group(1) not in var_assignments:
                var_assignments[m.group(1)] = m.group(2)
                continue
        
        # 变量引用链解析
        def _resolve_var(name, depth=0):
            if depth > 10:
                return None
            val = var_assignments.get(name)
            if val is None:
                return None
            m = re.match(r'^\$\{(\w+)\}$', val)
            if m:
                return _resolve_var(m.group(1), depth + 1)
            return val
        
        # ============================================================
        # 第2步：检测 for 循环，提取循环模式
        # ============================================================
        # 扫描函数体内外的所有行，检测 for 循环
        loop_expansion_steps = []  # 展开后的步骤
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            # 匹配 for var in $LIST_VAR; do
            for_match = re.match(
                r'^for\s+(\w+)\s+in\s+\$(\w+)\s*;\s*do\s*$', stripped
            )
            if not for_match:
                # 也可能是 for var in $LIST_VAR（后面另起一行 do）
                for_match = re.match(
                    r'^for\s+(\w+)\s+in\s+\$(\w+)\s*$', stripped
                )
            
            parts = None
            loop_var = None
            
            if for_match:
                loop_var = for_match.group(1)
                source_var = for_match.group(2)
                resolved = _resolve_var(source_var)
                if resolved:
                    parts = resolved.split()
            else:
                # 模式2：for var in val1 val2 val3; do（直接枚举值）
                direct_match = re.match(
                    r'^for\s+(\w+)\s+in\s+([^;$]+)\s*;\s*do\s*$', stripped
                )
                if not direct_match:
                    direct_match = re.match(
                        r'^for\s+(\w+)\s+in\s+([^;$]+)\s*$', stripped
                    )
                if direct_match:
                    loop_var = direct_match.group(1)
                    raw_values = direct_match.group(2).strip()
                    # 将枚举值拆分为列表
                    parts = [v.strip().strip('"').strip("'") for v in raw_values.split() if v.strip()]
            
            if not parts or not loop_var:
                continue
            line_no = i + 1
            
            # 查找 for 循环体：从 for 行之后，到下一个 done 之间的内容
            loop_body = []
            brace_count = 0
            for j in range(i + 1, len(lines)):
                l = lines[j].strip()
                # 检测 do（可能需要跳过 do 本身所在的行）
                if l == 'do' or l.startswith('do '):
                    continue
                if l == 'done' or l == 'done;' or l.startswith('done '):
                    break
                loop_body.append((j + 1, lines[j]))
            
            # 分析循环体：找出所有函数调用和内联命令
            for body_ln, body_line in loop_body:
                bl_stripped = body_line.strip()
                if bl_stripped.startswith('#'):
                    continue
                
                # 模式1：函数调用 flash_partition "$part" "$img" 或 flash_partition $part $img
                # 只要函数调用中包含 loop_var 参数的引用即可
                call_match = re.match(
                    r'^(\w+)\s+.*?\$' + re.escape(loop_var) + r'.*',
                    bl_stripped
                )
                # 确认是函数调用（函数名在 function_bodies 中）
                if call_match:
                    func_name = call_match.group(1)
                    func_body = function_bodies.get(func_name, [])
                    if not func_body:
                        continue
                    
                    # 从调用行提取位置参数（用于替换函数体中的 $1, $2, ...）
                    call_args = []  # [(raw_arg, resolved_value), ...]
                    # 提取调用参数：flash_partition "$part" "boot.img"
                    arg_part = bl_stripped.split(None, 1)
                    if len(arg_part) > 1:
                        args_str = arg_part[1].strip()
                        # 解析引号包裹的参数
                        for arg_match in re.finditer(r'"([^"]*)"|(\S+)', args_str):
                            arg_raw = (arg_match.group(1) or arg_match.group(2) or '')
                            # 如果参数是 $loop_var，用对应的 part_name 值
                            # 如果参数包含 $ 但不是 $loop_var（如 $part），暂不解析
                            clean_arg = arg_raw
                            if '$' + loop_var in clean_arg or '${' + loop_var + '}' in clean_arg:
                                # 在循环展开时每个 part_name 替换
                                call_args.append((clean_arg, None, True))  # 标记需要循环替换
                            else:
                                call_args.append((clean_arg, None, False))
                    
                    # 从函数体中提取 flash 行，用分区名替换 ${loop_var} 和 $loop_var
                    for (fb_ln, fb_line) in func_body:
                        if 'flash' not in fb_line.lower():
                            continue
                        for part_name in parts:
                            expanded = fb_line
                            # 替换函数体内的 $loop_var 引用（如 $img → boot.img）
                            expanded = expanded.replace(
                                '"${' + loop_var + '}"', '"' + part_name + '"'
                            )
                            expanded = expanded.replace(
                                '${' + loop_var + '}', part_name
                            )
                            expanded = expanded.replace(
                                '"$' + loop_var + '"', '"' + part_name + '"'
                            )
                            expanded = expanded.replace(
                                '$' + loop_var, part_name
                            )
                            # 替换同函数体内其他局部变量（如 $part），用无扩展名版本
                            base_name = part_name.rsplit('.', 1)[0] if '.' in part_name else part_name
                            # 查找函数体内的 local 变量赋值，用 base_name 替换
                            # 简单做法：对函数体中 $part 或 ${part} 做替换  
                            expanded = expanded.replace(
                                '"${part}"', '"' + base_name + '"'
                            )
                            expanded = expanded.replace(
                                '${part}', base_name
                            )
                            expanded = expanded.replace(
                                '"$part"', '"' + base_name + '"'
                            )
                            expanded = expanded.replace(
                                '$part', base_name
                            )
                            
                            # 对展开行做预清理：移除 if/if ! 前缀
                            pre = expanded.strip()
                            pre = re.sub(r'^if\s+!\s*', '', pre)
                            pre = re.sub(r'^if\s+', '', pre)
                            loop_expansion_steps.append((body_ln, pre))
                    continue
                
                # 模式2：内联 fastboot 命令（直接有 $loop_var 的行，形如 "$FASTBOOT" flash "${part}_a" ...）
                if '$' + loop_var in bl_stripped or '${' + loop_var + '}' in bl_stripped:
                    # 用 fb_pattern 检测是否包含 fastboot 命令
                    fb_check = re.compile(
                        r'(?:"\s*)?(?:\$FASTBOOT"?|\$\{FASTBOOT\}"?|\bfastboot\b)\s+(flash|erase|reboot(?:-bootloader)?|set_active|boot|devices|-w)',
                        re.I
                    )
                    if not fb_check.search(bl_stripped):
                        continue
                    for part_name in parts:
                        expanded = bl_stripped
                        expanded = expanded.replace(
                            '"${' + loop_var + '}"', part_name
                        )
                        expanded = expanded.replace(
                            '${' + loop_var + '}', part_name
                        )
                        expanded = expanded.replace(
                            '"$' + loop_var + '"', part_name
                        )
                        expanded = expanded.replace(
                            '$' + loop_var, part_name
                        )
                        loop_expansion_steps.append((body_ln, expanded))
        
        # ============================================================
        # 第3步：从原文提取 fastboot 行
        # ============================================================
        fb_pattern = re.compile(
            r'(?:"\s*)?(?:\$FASTBOOT"?|\$\{FASTBOOT\}"?|\bfastboot\b)\s+(flash|erase|reboot(?:-bootloader)?|set_active|boot|devices|-w)',
            re.I
        )
        
        # 函数体内行号集合（用于检测是否在函数体内）
        func_line_nos = set()
        for func_name, body in function_bodies.items():
            for (ln, _) in body:
                func_line_nos.add(ln)
        
        raw_lines = []
        for i, line in enumerate(lines):
            line_no = i + 1
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            if re.match(r'^[a-zA-Z_]\w*\s*\(\s*\)\s*\{?\s*$', stripped):
                continue
            if re.match(r'^(echo|log|cat|read|exit|return|eval|getopt)\b', stripped, re.I):
                continue
            if re.match(r'^-\w', stripped):
                continue
            if fb_pattern.search(stripped):
                # 如果在函数体内，检查是否包含未展开的函数参数占位符或辅助命令
                if line_no in func_line_nos:
                    # 包含 $part、$1 等位置参数占位符的行跳过（由第2步展开处理）
                    if re.search(r'\$\d\b|\$part\b|\$img\b|\$\{part\}\b|\$\{img\}\b', stripped):
                        continue
                    # 函数体内的 devices 命令（设备检测辅助函数）跳过
                    if 'devices' in stripped.lower():
                        continue
                raw_lines.append((line_no, stripped))
        
        def _clean_and_parse(raw):
            """清理原始行并解析为 HydraStep"""
            cleaned = raw
            # $FASTBOOT / "$FASTBOOT" / ${FASTBOOT} -> fastboot
            cleaned = re.sub(r'"\s*\$FASTBOOT"\s*', 'fastboot ', cleaned)
            cleaned = re.sub(r'"\s*\$FASTBOOT', 'fastboot', cleaned)
            cleaned = re.sub(r'\$FASTBOOT"\s*', 'fastboot ', cleaned)
            cleaned = re.sub(r'\$FASTBOOT', 'fastboot', cleaned)
            cleaned = re.sub(r'"\s*\$\{FASTBOOT\}"\s*', 'fastboot ', cleaned)
            cleaned = re.sub(r'"\s*\$\{FASTBOOT\}', 'fastboot', cleaned)
            cleaned = re.sub(r'\$\{FASTBOOT\}"\s*', 'fastboot ', cleaned)
            cleaned = re.sub(r'\$\{FASTBOOT\}', 'fastboot', cleaned)
            
            # 移除 if/if ! 前缀和 ; then
            cleaned = re.sub(r'^if\s+!\s*', '', cleaned)
            cleaned = re.sub(r'^if\s+', '', cleaned)
            cleaned = re.sub(r'\s*;\s*then\s*$', '', cleaned)
            
            # 移除重定向和错误处理
            cleaned = re.sub(r'\s*>>?\s*\S+(?:\s+2>&1)?', '', cleaned)
            cleaned = re.sub(r'\s+2>&1', '', cleaned)
            cleaned = re.sub(r'\s*\|\|\s*(?:log|true|:)\s*".*?"', '', cleaned)
            cleaned = re.sub(r'\s*\|\|\s*\w+.*', '', cleaned)
            cleaned = re.sub(r'\s*&&\s*\w+\s*".*?"', '', cleaned)
            
            # 移除行尾注释
            cleaned = re.sub(r'\s+#.*$', '', cleaned)
            
            # 清理多余空格和引号
            cleaned = re.sub(r'\s{2,}', ' ', cleaned)
            cleaned = cleaned.strip().strip('"')
            
            if not cleaned:
                return None
            
            # 解析 fastboot 命令
            m = re.match(
                r'(?:fastboot(?:\.exe)?)\s+'
                r'(flash|erase|reboot(?:-bootloader)?|set_active|boot|devices|-w|getvar|oem)'
                r'(?:\s+(.*))?$',
                cleaned, re.I
            )
            if not m:
                return None
            
            cmd_type = m.group(1).lower()
            rest = (m.group(2) or '').strip()
            
            step_type = cmd_type
            part = ''
            fname = ''
            params = ''
            
            if cmd_type == 'flash':
                parts2 = rest.split(None, 1) if rest else []
                if parts2:
                    part = parts2[0].strip('"')
                    if len(parts2) > 1:
                        fname = parts2[1].strip('"')
            elif cmd_type == 'erase':
                part = rest.strip('"') if rest else ''
            elif cmd_type == 'reboot':
                part = rest.strip('"') if rest else 'system'
                # reboot-bootloader → part='bootloader'  
                # （正则中已整体匹配 reboot-bootloader，但这里兼容无空格情况）
                if part.startswith('-'):
                    part = part.lstrip('-')
            elif cmd_type == 'reboot-bootloader':
                step_type = 'reboot'
                part = 'bootloader'
            elif cmd_type == 'set_active':
                part = rest.strip('"') if rest else ''
            elif cmd_type == '-w':
                step_type = 'erase'
                part = 'userdata'
                params = '-w'
            elif cmd_type == 'devices':
                step_type = 'devices'
            elif cmd_type == 'boot':
                fname = rest.strip('"') if rest else ''
            
            return HydraStep(
                type=step_type, part=part, fileName=fname,
                params=params, raw=raw, risk='B',
            )
        
        # ============================================================
        # 第4步：合并步骤（管线私有去重）
        # ============================================================
        steps = []
        seen = set()  # 仅防止完全相同的行+行号组合重复
        
        # 先加 for 循环展开的步骤（作为基础）
        for line_no, expanded_raw in loop_expansion_steps:
            key = (line_no, expanded_raw)
            if key in seen:
                continue
            seen.add(key)
            step = _clean_and_parse(expanded_raw)
            if step:
                step.line_no = line_no
                steps.append(step)
        
        # 再加直接提取的步骤（补充没有循环体的命令）
        for line_no, raw in raw_lines:
            key = (line_no, raw)
            if key in seen:
                continue
            seen.add(key)
            step = _clean_and_parse(raw)
            if step:
                step.line_no = line_no
                steps.append(step)
        
        # 最终语义去重（与其它管线保持一致）
        steps = self._dedup_simple(steps)
        return steps, None

    def _parse_legacy(self, content, script_type, rom_dir, script_path):
        """legacy：返回空列表，回退旧版"""
        return [], None

    # ================================================================
    # 内部工具
    # ================================================================

    def _run_tracer(self, content, script_type, rom_dir, script_path):
        """执行追踪。"""
        tracer_steps = []
        if script_type == "sh":
            try:
                if script_path and os.path.isfile(script_path):
                    tracer_steps = self.execution_tracer.trace(
                        script_path=script_path, rom_dir=rom_dir,
                        timeout=self.options.sh_tracer_timeout,
                    )
                else:
                    tracer_steps = self.execution_tracer.trace_script_content(
                        content=content,
                        work_dir=rom_dir or os.path.dirname(script_path) if script_path else "/tmp",
                        timeout=self.options.sh_tracer_timeout,
                    )
            except Exception:
                pass
        elif script_type == "bat":
            try:
                tracer_steps = self.bat_execution_tracer.trace(
                    script_path=script_path if os.path.isfile(script_path) else "",
                    content=content if not os.path.isfile(script_path) else "",
                    rom_dir=rom_dir,
                )
            except Exception:
                pass
        return tracer_steps

    def _step_semantic_key(self, s) -> tuple:
        t = s.type.strip().lower() if s.type else ""
        p = s.part.strip().lower() if s.part else ""
        f_raw = s.fileName.strip().lower() if s.fileName else ""
        f = os.path.basename(f_raw) if f_raw else ""
        params_norm = s.params.strip().lower() if s.params and t == "erase" else ""
        cond_norm = s.condition.strip().lower()[:40] if s.condition else ""
        loop_norm = s.loop.strip().lower()[:40] if s.loop else ""
        return (t, p, f, params_norm, cond_norm, loop_norm)


# 便捷工厂
_engine_instance = None

# 兼容别名（旧名为 HydraEngine）
HydraEngine = Engine


def get_engine() -> Engine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = Engine()
    return _engine_instance


# 兼容旧名 get_hydra_engine（必须在 get_engine 定义之后）
get_hydra_engine = get_engine


__all__ = [
    "HydraEngine",
    "Engine",
    "HydraStep",
    "HydraParseResult",
    "get_engine",
]