"""
BAT 虚拟沙箱执行器
模拟执行归一化指令流，拦截 fastboot/adb 调用并收集步骤
"""
import os
import re
import fnmatch
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from .normalizer import NormalizedCmd


@dataclass
class CallFrame:
    """调用栈帧"""
    cmds: List[NormalizedCmd]
    pc: int = 0
    label_index: Dict[str, int] = field(default_factory=dict)


# 默认视为存在的镜像文件后缀
IMAGE_EXTS = ('.img', '.bin', '.mbn', '.elf', '.melf', '.sin', '.raw')
# 常用文件名
SPECIAL_FILES = {'anti.txt', 'flash_all.bat', 'flash_all.sh',
                 'flash_all_except_storage.bat', 'flash_all_lock.bat',
                 'misc.bin', 'gpt_both0.bin', 'partition.xml',
                 'rawprogram0.xml', 'patch0.xml',
                 'boot.img', 'recovery.img', 'system.img', 'vendor.img',
                 'super.img', 'product.img', 'vbmeta.img', 'dtbo.img',
                 'userdata.img', 'cache.img', 'persist.img', 'modem.img'}


class BatSandbox:
    """BAT 脚本虚拟沙箱"""
    
    MAX_ITERATIONS = 50_000  # 防死循环
    MAX_CALL_DEPTH = 20      # 最大调用栈深度
    
    def __init__(self, device_info: Optional[Dict] = None, rom_dir: str = '',
                 extra_args: str = ''):
        self.env: Dict[str, str] = {
            'errorlevel': '0',
            'random': str(os.urandom(2)[0]),
            'cd': rom_dir or '.',
        }
        if device_info:
            self.env.update(device_info)
        
        self.rom_dir = rom_dir
        self.extra_args = extra_args  # %* 展开值
        self.trace: List[dict] = []
        self._call_stack: List[CallFrame] = []
        self._script_cache: Dict[str, List[NormalizedCmd]] = {}
        self._iter_count = 0
        self._delayed_expansion = False  # setlocal enabledelayedexpansion 标志
        
        # ═══ 交互式 / 分支模拟支持 ═══
        self.interactive_vars: dict = {}      # var_name -> {prompt, branches: [value, ...]}
        self.branch_mode: bool = False        # 是否处于分支穷举模式
        self._branches_cache: dict = {}       # var_name -> [value, ...] 缓存
    
    def run(self, cmds: List[NormalizedCmd]) -> List[dict]:
        """执行归一化指令流，返回刷机步骤列表
        
        自动检测交互式脚本：
        - 有交互点 → 进入分支模拟模式，穷举所有分支并合并结果
        - 无交互点 → 正常执行
        """
        # 1. 检测交互变量
        self._scan_interactive_vars(cmds)
        
        if self.interactive_vars:
            return self._run_branches(cmds)
        
        # 2. 普通模式：直接执行
        return self._run_single(cmds)
    
    def _run_single(self, cmds: List[NormalizedCmd], max_gotos: int = 5, start_pc: int = 0) -> List[dict]:
        """单次执行指令流，返回步骤列表
        
        Args:
            max_gotos: 最大 goto 跳转次数，防止交互式脚本无限循环
            start_pc: 起始指令位置，用于跳过检测循环段直达交互菜单
        """
        self.trace = []
        self._iter_count = 0
        self._goto_count = 0
        self._max_gotos = max_gotos
        self._visited_labels = set()  # 已跳转过的标签（防循环）
        
        # 初始化调用栈（从指定位置开始）
        self._call_stack = [self._make_frame(cmds, pc=start_pc)]
        
        while self._call_stack:
            frame = self._call_stack[-1]
            
            self._iter_count += 1
            if self._iter_count > self.MAX_ITERATIONS:
                raise RuntimeError(
                    f"BAT 沙箱超过最大迭代次数 {self.MAX_ITERATIONS}，"
                    f"可能陷入死循环"
                )
            
            if frame.pc >= len(frame.cmds):
                self._call_stack.pop()
                continue
            
            cmd = frame.cmds[frame.pc]
            cmd = self._expand_cmd(cmd)
            
            jump = self._execute(cmd, frame)
            if jump == 'exit':
                break
            elif jump is not None:
                frame.pc = jump
            else:
                frame.pc += 1
        
        return self.trace
    
    def _scan_interactive_vars(self, cmds: List[NormalizedCmd]):
        """扫描指令流中的交互变量和所有可能的分支值"""
        self.interactive_vars = {}
        interactive_var_names = set()
        
        # 第一遍：收集所有 interactive 变量名
        for cmd in cmds:
            if cmd.type == 'INTERACTIVE':
                var_name = cmd.args[0].lower()
                prompt = cmd.args[1] if len(cmd.args) > 1 else ''
                interactive_var_names.add(var_name)
                self.interactive_vars[var_name] = {
                    'prompt': prompt,
                    'branches': set(),
                }
        
        if not interactive_var_names:
            return
        
        # 第二遍：扫描所有 IF_EQ 对比这些变量的分支值（递归）
        self._collect_branches(cmds, interactive_var_names)
        # 对每个变量补一个默认空值分支（用户不选择时）
        for var_name, info in self.interactive_vars.items():
            if not info['branches']:
                info['branches'] = {''}
    
    def _collect_branches(self, cmds: List, interactive_var_names: set):
        """递归收集交互变量的所有可能分支值（不重复初始化）"""
        for cmd in cmds:
            if isinstance(cmd, NormalizedCmd):
                if cmd.type == 'IF_EQ':
                    var_expr = cmd.args[0].lower()
                    expected_val = cmd.args[1]
                    var_clean = var_expr.strip().strip('%')
                    if var_clean in interactive_var_names:
                        self.interactive_vars[var_clean]['branches'].add(expected_val)
                elif cmd.type in ('BLOCK', 'BLOCK_ELSE'):
                    header = cmd.args[0]
                    if header.type == 'IF_EQ':
                        var_expr = header.args[0].lower()
                        expected_val = header.args[1]
                        var_clean = var_expr.strip().strip('%')
                        if var_clean in interactive_var_names:
                            self.interactive_vars[var_clean]['branches'].add(expected_val)
                    for sub in cmd.args[1:]:
                        if isinstance(sub, list):
                            self._collect_branches(sub, interactive_var_names)
    
    def _exec_set_in_block(self, sandbox, cmds):
        """递归执行块内的 SET 指令（用于建立环境变量）"""
        if not isinstance(cmds, list):
            return
        for cmd in cmds:
            if isinstance(cmd, NormalizedCmd):
                if cmd.type == 'SET':
                    sandbox._handle_set(sandbox._expand_cmd(cmd))
                elif cmd.type in ('BLOCK', 'BLOCK_ELSE'):
                    self._exec_set_in_block(sandbox, cmd.args[1])
                    if len(cmd.args) > 2:
                        self._exec_set_in_block(sandbox, cmd.args[2])
    
    def _run_branches(self, cmds: List[NormalizedCmd]) -> List[dict]:
        """分支模拟模式：只对第一个交互变量的每个分支值穷举执行"""
        # 找到第一个交互变量（主菜单选择）
        first_var = None
        first_var_info = None
        for cmd in cmds:
            if cmd.type == 'INTERACTIVE':
                var_name = cmd.args[0].lower()
                if var_name in self.interactive_vars:
                    first_var = var_name
                    first_var_info = self.interactive_vars[var_name]
                    break
        
        if not first_var or not first_var_info:
            return self._run_single(cmds)
        
        # 扫描交互入口 label（跳过检测循环段）
        start_pc = 0
        for i, cmd in enumerate(cmds):
            if cmd.type == 'INTERACTIVE':
                for j in range(i-1, -1, -1):
                    if cmds[j].type == 'LABEL':
                        start_pc = j
                        break
                break
        
        # 预执行所有非交互指令（建立必要的环境变量，如 TOOL_PATH 等）
        init_sandbox = BatSandbox(rom_dir=self.rom_dir)
        for cmd in cmds[:start_pc]:
            if cmd.type == 'SET':
                init_sandbox._handle_set(init_sandbox._expand_cmd(cmd))
            elif cmd.type in ('BLOCK', 'BLOCK_ELSE'):
                self._exec_set_in_block(init_sandbox, cmd.args[1])
                if len(cmd.args) > 2:
                    self._exec_set_in_block(init_sandbox, cmd.args[2])
        base_env = {k: v for k, v in init_sandbox.env.items() 
                    if k not in ('errorlevel', 'random', 'cd')}
        
        all_results = []
        
        for branch_value in sorted(first_var_info['branches']):
            sandbox = BatSandbox(
                device_info={**base_env, **{k: v for k, v in self.env.items() 
                            if k not in ('errorlevel', 'random', 'cd')}},
                rom_dir=self.rom_dir,
            )
            sandbox.env[first_var] = str(branch_value)
            sandbox._delayed_expansion = self._delayed_expansion
            
            steps = sandbox._run_single(cmds, max_gotos=15, start_pc=start_pc)
            
            all_results.append({
                'choice': f'{first_var}={branch_value}',
                'var_name': first_var,
                'branch_value': branch_value,
                'prompt': first_var_info['prompt'],
                'steps': steps,
                'step_count': len(steps),
            })
        
        return self._merge_branch_results(all_results)
    
    def _merge_branch_results(self, branch_results: List[dict]) -> List[dict]:
        """合并多个分支的结果，去重后返回"""
        seen = set()
        merged = []
        branches_meta = []
        
        for br in branch_results:
            branches_meta.append({
                'choice': br['choice'],
                'prompt': br['prompt'],
                'step_count': br['step_count'],
            })
            for step in br['steps']:
                part = step.get('part', '') or step.get('target', '') or step.get('slot', '') or step.get('action', '')
                key = (step.get('type', ''), part, step.get('fileName', ''))
                if key not in seen:
                    seen.add(key)
                    step['_branch_source'] = br['choice']
                    merged.append(step)
        
        # 在最前面插入交互元数据
        merged.insert(0, {
            '_meta': 'interactive_merged',
            'branches': branches_meta,
            'total_raw_steps': sum(br['step_count'] for br in branch_results),
            'merged_steps': len(merged),
        })
        
        return merged
    
    def _execute(self, cmd: NormalizedCmd, frame: CallFrame) -> Optional[Any]:
        """执行单条指令，返回跳转目标/exit/None"""
        # 展开变量（!VAR! 延迟展开等），确保在递归调用中也生效
        cmd = self._expand_cmd(cmd)
        
        if cmd.type == 'SET':
            # 检测 setlocal enabledelayedexpansion
            if cmd.args[0].lower() == 'local' and 'enabledelayedexpansion' in cmd.args[1].lower():
                self._delayed_expansion = True
            self._handle_set(cmd)
        elif cmd.type == 'GOTO':
            return self._handle_goto(cmd, frame)
        elif cmd.type == 'CALL':
            return self._handle_call(cmd, frame)
        elif cmd.type in ('BLOCK', 'BLOCK_ELSE'):
            return self._handle_block(cmd, frame)
        elif cmd.type == 'IF_EXIST':
            return self._handle_if_exist(cmd, frame)
        elif cmd.type == 'IF_EQ':
            return self._handle_if_eq(cmd, frame)
        elif cmd.type == 'IF_ERRORLEVEL':
            return self._handle_if_errorlevel(cmd, frame)
        elif cmd.type == 'FOR':
            return self._handle_for(cmd, frame)
        elif cmd.type == 'EXEC':
            # 展开变量（确保递归调用中也展开）
            if self._delayed_expansion:
                expanded_args = []
                for a in cmd.args:
                    if isinstance(a, str):
                        expanded_args.append(self._resolve_vars(a))
                    else:
                        expanded_args.append(a)
                cmd = NormalizedCmd(type='EXEC', args=expanded_args, flags=cmd.flags,
                                    raw=cmd.raw, lineno=cmd.lineno)
            
            # 检测 setlocal enabledelayedexpansion
            if len(cmd.args) >= 2 and cmd.args[0].lower() == 'setlocal' and 'enabledelayedexpansion' in cmd.args[1].lower():
                self._delayed_expansion = True
            self._handle_exec(cmd)
        elif cmd.type == 'INTERACTIVE':
            # 交互变量：在分支模拟模式下，沙箱已经预先注入了分支值
            # 这里不做任何事，让指令流继续执行
            # _run_branches 中隔离沙箱会通过 env 设好分支值
            # 如果 env 中没有这个变量（非分支模式），就设为空字符串
            var_name = cmd.args[0].lower()
            if var_name not in self.env:
                self.env[var_name] = ''
        elif cmd.type == 'EXIT':
            return 'exit'
        # LABEL 不执行，继续下一条
        return None
    
    # ========== 多行块处理 ==========
    
    def _handle_block(self, cmd: NormalizedCmd, frame: CallFrame) -> Optional[Any]:
        """执行多行块 (if ... ( ... ) / for ... do ( ... ))"""
        header_cmd = cmd.args[0]
        body_cmds = cmd.args[1]
        else_cmds = cmd.args[2] if cmd.type == 'BLOCK_ELSE' else []
        
        if header_cmd.type == 'IF_EXIST':
            # 直接判断条件
            not_exist, path, _action = header_cmd.args
            path = self._resolve_vars(path)
            path = self._resolve_path(path)
            exists = self._mock_file_exists(path)
            condition_met = (not exists) if not_exist else exists
            
            if condition_met:
                for bcmd in body_cmds:
                    self._execute(self._expand_cmd(bcmd), frame)
            elif else_cmds:
                for bcmd in else_cmds:
                    self._execute(self._expand_cmd(bcmd), frame)
        
        elif header_cmd.type == 'IF_EQ':
            var_expr, expected_val, _action = header_cmd.args
            actual_val = self.env.get(var_expr.lower(), '')
            expected_val = self._resolve_vars(expected_val)
            condition_met = (actual_val.strip('"') == expected_val.strip('"'))
            
            if condition_met:
                for bcmd in body_cmds:
                    self._execute(self._expand_cmd(bcmd), frame)
            elif else_cmds:
                for bcmd in else_cmds:
                    self._execute(self._expand_cmd(bcmd), frame)
        
        elif header_cmd.type == 'IF_ERRORLEVEL':
            not_flag, threshold, _action = header_cmd.args
            current = int(self.env.get('errorlevel', '0'))
            condition_met = (current >= threshold) if not not_flag else (current < threshold)
            
            if condition_met:
                for bcmd in body_cmds:
                    self._execute(self._expand_cmd(bcmd), frame)
            elif else_cmds:
                for bcmd in else_cmds:
                    self._execute(self._expand_cmd(bcmd), frame)
        
        elif header_cmd.type == 'FOR':
            loop_type, var_name, collection, _body = header_cmd.args
            collection_expanded = self._resolve_vars(collection)
            items = self._resolve_collection(loop_type, collection_expanded, header_cmd.flags)
            
            env_key = var_name.strip('%').lower() if '%' in var_name else var_name.lower()
            
            # 【修复】：FOR 循环环境快照隔离
            # 保存进入前的 env 快照，防止内层循环意外污染外层变量
            env_snapshot = self.env.copy()
            
            for item in items:
                self.env[env_key] = item
                
                # 检查 SKIP_LIST 过滤（只在文件迭代时应用）
                if env_key == 'f':
                    skip_list = self.env.get('skip_list', '')
                    if skip_list:
                        basename = os.path.basename(item)
                        name_no_ext = os.path.splitext(basename)[0]
                        if name_no_ext in skip_list.split():
                            self.env['name'] = name_no_ext
                            self.env['skip'] = '1'
                            continue
                
                # 执行 body 前清除 name/skip，让内部 SET 重新写入
                self.env.pop('name', None)
                self.env.pop('skip', None)
                
                for bcmd in body_cmds:
                    bcmd_expanded = self._expand_for_body_cmd(bcmd, env_key, item)
                    self._execute(bcmd_expanded, frame)
            
            # FOR 循环结束后恢复环境快照（保留内层需要传递的 skip 变量）
            self.env = env_snapshot
            if 'skip' in self.env:
                self.env['skip'] = self.env.get('skip', '0')
        
        return None
    
    def _expand_for_body_cmd(self, cmd: NormalizedCmd, var_name: str, var_value: str) -> NormalizedCmd:
        """展开 for 循环 body 中的 %%var 变量
        只展开 %% 变量，不展开 %VAR% 和 !VAR!（它们由 _execute 阶段的 _expand_cmd 处理）
        """
        expanded_args = []
        for a in cmd.args:
            if isinstance(a, str):
                # %%~dpX → 目录路径
                a = re.sub(r'%%~dp([a-z])', lambda m: os.path.dirname(var_value) + '/', a)
                # %%~nX → 文件名（不含扩展名）
                a = re.sub(r'%%~n([a-z])?', lambda m: os.path.splitext(os.path.basename(var_value))[0], a)
                # %%~fX? → 完整路径（X可选）
                a = re.sub(r'%%~f([a-z])?', lambda m: var_value, a)
                # %%~xX → 扩展名
                a = re.sub(r'%%~x([a-z])', lambda m: os.path.splitext(var_value)[1], a)
                # %%p → var_value（精确匹配，防止误伤 !name!）
                a = re.sub(rf'%%{var_name}(?![a-zA-Z])', var_value, a)
                # 展开 %VAR%（不展开 !VAR!，留给 _execute 阶段）
                a = re.sub(r'%(\w+)%', lambda m: self.env.get(m[1].lower(), m[0]), a)
                expanded_args.append(a)
            else:
                expanded_args.append(a)
        return NormalizedCmd(type=cmd.type, args=expanded_args, flags=cmd.flags,
                             raw=cmd.raw, lineno=cmd.lineno)
    
    # ========== 指令处理器 ==========
    
    def _handle_set(self, cmd: NormalizedCmd):
        var = cmd.args[0].lower()
        val = self._resolve_vars(cmd.args[1])
        self.env[var] = val
    
    def _handle_goto(self, cmd: NormalizedCmd, frame: CallFrame) -> int:
        self._goto_count += 1
        if self._goto_count > self._max_gotos:
            return len(frame.cmds)
        
        label = cmd.args[0].lower()
        
        # 分支模式下的防循环机制
        if self.interactive_vars:
            # 跳过检测类循环标签
            if label.startswith('check_'):
                return frame.pc + 1
            # 同一标签只允许跳转一次，防止 sub_menu / logic_menu 等循环
            if label in self._visited_labels:
                # 如果跳转到已访问的标签（循环），直接结束执行
                return len(frame.cmds)
        
        self._visited_labels.add(label)
        
        if label in frame.label_index:
            return frame.label_index[label] + 1
        return len(frame.cmds)
    
    def _handle_call(self, cmd: NormalizedCmd, frame: CallFrame) -> Optional[int]:
        target = cmd.args[0]
        
        if len(self._call_stack) >= self.MAX_CALL_DEPTH:
            return None  # 超过深度限制，跳过
        
        if target.startswith(':'):
            # 内部标签调用
            label = target[1:].lower()
            if label in frame.label_index:
                return_pc = frame.pc + 1
                sub_frame = self._make_frame(frame.cmds, pc=frame.label_index[label])
                sub_frame.label_index = frame.label_index
                self._call_stack.append(sub_frame)
                return sub_frame.pc  # 从标签行开始执行
            return None
        else:
            # 外部脚本调用
            sub_cmds = self._load_script(target)
            if sub_cmds:
                sub_frame = self._make_frame(sub_cmds, pc=0)
                self._call_stack.append(sub_frame)
                return 0
            return None
    
    def _handle_if_exist(self, cmd: NormalizedCmd, frame: CallFrame) -> Optional[Any]:
        not_exist, path, action = cmd.args
        path = self._resolve_vars(path)
        path = self._resolve_path(path)
        exists = self._mock_file_exists(path)
        condition_met = (not exists) if not_exist else exists
        
        if condition_met:
            return self._resolve_action(action, frame)
        return None
    
    def _handle_if_eq(self, cmd: NormalizedCmd, frame: CallFrame) -> Optional[Any]:
        var_expr, expected_val, action = cmd.args
        actual_val = self.env.get(var_expr.lower(), '')
        expected_val = self._resolve_vars(expected_val)
        condition_met = (actual_val.strip('"') == expected_val.strip('"'))
        
        if condition_met:
            return self._resolve_action(action, frame)
        return None
    
    def _handle_if_errorlevel(self, cmd: NormalizedCmd, frame: CallFrame) -> Optional[Any]:
        not_flag, threshold, action = cmd.args
        current = int(self.env.get('errorlevel', '0'))
        condition_met = (current >= threshold) if not not_flag else (current < threshold)
        
        if condition_met:
            return self._resolve_action(action, frame)
        return None
    
    def _handle_for(self, cmd: NormalizedCmd, frame: CallFrame) -> None:
        """展开 for 循环"""
        loop_type, var_name, collection, body = cmd.args
        items = self._resolve_collection(loop_type, collection, cmd.flags)
        
        # for 循环变量 %%i 在 body 中以 %%i 出现，沙箱环境用 %i% 作为环境变量键
        env_key = var_name.strip('%').lower() if '%' in var_name else var_name.lower()
        for item in items:
            self.env[env_key] = item
            # body 中的 %%p 替换为 %p% 以便 _resolve_vars 展开
            body_prepared = re.sub(r'%%(\w)', r'%\1%', body)
            body_expanded = self._resolve_vars(body_prepared)
            
            # body 可能含 fastboot，重新归一化执行
            from .normalizer import BatNormalizer
            normalizer = BatNormalizer()
            body_cmds = normalizer.normalize(body_expanded)
            
            for bcmd in body_cmds:
                bcmd = self._expand_cmd(bcmd)
                self._execute(bcmd, frame)
    
    def _handle_exec(self, cmd: NormalizedCmd):
        """拦截 fastboot / adb 命令"""
        # 展开变量
        parts = []
        for a in cmd.args:
            if isinstance(a, str):
                a = re.sub(r'!(\w+)!', lambda m: self.env.get(m[1].lower(), m[0]), a)
                a = re.sub(r'%(\w+)%', lambda m: self.env.get(m[1].lower(), m[0]), a)
                parts.append(a)
            else:
                parts.append(a)
        cmd = NormalizedCmd(type=cmd.type, args=parts, raw=cmd.raw, lineno=cmd.lineno)
        
        parts = cmd.args
        if not parts:
            return
        
        # 【修复】：拦截 if 语句，评估条件后再执行 set
        first = parts[0].lower()
        if first == 'if':
            cmd_str = ' '.join(str(p) for p in parts)
            # 匹配 if [/i] "left"=="right" set X=Y
            m = re.match(
                r'if\s+(/i\s+)?["\']?([^"\']+)["\']?\s*==\s*["\']?([^"\']+)["\']?\s+set\s+["\']?(\w+)=([^"\']*)["\']?',
                cmd_str, re.IGNORECASE
            )
            if m:
                case_insensitive = bool(m[1])
                left = m[2].strip().strip('"').strip("'")
                right = m[3].strip().strip('"').strip("'")
                var_name = m[4].strip()
                var_value = m[5].strip()
                
                if case_insensitive:
                    condition_met = (left.lower() == right.lower())
                else:
                    condition_met = (left == right)
                
                if condition_met:
                    self.env[var_name.lower()] = var_value
            return  # 不记录到 trace
        
        binary = parts[0].lower().replace('\\', '/').split('/')[-1]
        
        if 'fastboot' in binary:
            step = self._intercept_fastboot(parts[1:])
            if step:
                self.trace.append(step)
                self.env['errorlevel'] = '0'
        elif 'adb' in binary:
            step = self._intercept_adb(parts[1:])
            if step:
                self.trace.append(step)
    
    # ========== fastboot/adb 拦截 ==========
    
    def _intercept_fastboot(self, args: List[str]) -> Optional[dict]:
        if not args:
            return None
        
        # 跳过空字符串（%* 展开为空的残留）和全局参数（以 -- 开头）
        global_params = []
        skipped_placeholders = []
        while args and (not args[0] or args[0].startswith('--') or args[0] == '%*'):
            if not args[0]:
                pass  # 空字符串，直接跳过
            elif args[0].startswith('--'):
                global_params.append(args[0])
            else:
                skipped_placeholders.append(args[0])
            args = args[1:]
        
        if not args:
            return None
        
        action = args[0].lower().replace(':', '')
        
        if action == 'flash':
            extra_params = ' '.join(args[3:]) if len(args) > 3 else ''
            global_str = ' '.join(global_params) if global_params else ''
            combined = f"{global_str} {extra_params}".strip()
            return {
                'type': 'flash',
                'part': args[1] if len(args) > 1 else '',
                'fileName': args[2] if len(args) > 2 else '',
                'params': combined,
                'confidence': 'certain',
            }
        elif action == 'erase':
            return {
                'type': 'erase',
                'part': args[1] if len(args) > 1 else '',
                'params': ' '.join(args[2:]) if len(args) > 2 else '',
                'confidence': 'certain',
            }
        elif action == 'reboot':
            # args[0] 是 reboot 本身，args[1] 是目标(如 fastboot/bootloader)
            # 可能还有更多参数通过空格分隔，全部拼接
            target_parts = args[1:] if len(args) > 1 else ['']
            target = ' '.join(target_parts)
            return {'type': 'reboot', 'target': target, 'confidence': 'certain'}
        elif action == 'reboot-bootloader':
            return {'type': 'reboot', 'target': 'bootloader', 'confidence': 'certain'}
        elif action == 'getvar':
            return {'type': 'getvar', 'part': args[1] if len(args) > 1 else '', 'confidence': 'certain'}
        elif action == 'set_active' or action == '--set-active':
            return {'type': 'set_active', 'slot': args[1] if len(args) > 1 else '', 'confidence': 'certain'}
        elif action in ('oem', 'flashing'):
            return {
                'type': 'oem',
                'action': args[1] if len(args) > 1 else '',
                'params': ' '.join(args[2:]) if len(args) > 2 else '',
                'confidence': 'certain',
            }
        elif action == 'format':
            return {'type': 'format', 'part': args[1] if len(args) > 1 else '', 'confidence': 'certain'}
        elif action == '-w':
            return {'type': 'wipe', 'part': 'userdata', 'confidence': 'certain'}
        else:
            return {
                'type': action,
                'params': ' '.join(args[1:]) if len(args) > 1 else '',
                'confidence': 'estimated',
            }
    
    def _intercept_adb(self, args: List[str]) -> Optional[dict]:
        if not args:
            return None
        return {
            'type': 'adb',
            'action': args[0],
            'params': ' '.join(args[1:]) if len(args) > 1 else '',
            'confidence': 'certain',
        }
    
    # ========== 辅助方法 ==========
    
    def _resolve_action(self, action: str, frame: CallFrame) -> Optional[Any]:
        """解析 if 条件成立时要执行的 action"""
        action = action.strip()
        
        m = re.match(r'(?i)goto\s+:?(\w+)', action)
        if m:
            label = m[1].lower()
            if label in frame.label_index:
                return frame.label_index[label] + 1
            return len(frame.cmds)
        
        if re.match(r'(?i)exit(\s+/b)?', action):
            return 'exit'
        
        # inline 命令（如 if exist boot.img fastboot flash boot boot.img）
        if re.match(r'(?i)(fastboot|%fastboot%|adb|%adb%)', action):
            clean = action.replace('%FASTBOOT%', 'fastboot').replace('%fastboot%', 'fastboot')
            clean = clean.replace('%ADB%', 'adb').replace('%adb%', 'adb')
            parts = self._smart_split(clean)
            self._handle_exec(NormalizedCmd('EXEC', args=parts))
        
        return None
    def _expand_cmd(self, cmd: NormalizedCmd) -> NormalizedCmd:
        """展开命令中的 %VAR% 变量"""
        expanded = []
        for a in cmd.args:
            if isinstance(a, str):
                expanded.append(self._resolve_vars(a))
            else:
                expanded.append(a)
        expanded_flags = {}
        for k, v in cmd.flags.items():
            expanded_flags[k] = self._resolve_vars(v) if isinstance(v, str) else v
        return NormalizedCmd(type=cmd.type, args=expanded, flags=expanded_flags,
                             raw=cmd.raw, lineno=cmd.lineno)
    def _resolve_vars(self, text: str) -> str:
        """展开 %VAR%、!VAR! 和 %* 表达式"""
        # 先展开 %~dp0 这种特殊变量
        if '%~dp0' in text:
            text = text.replace('%~dp0', (self.rom_dir or '.').replace('\\', '/') + '/')
        
        # 展开 %* （全部命令行参数）
        if '%*' in text:
            text = text.replace('%*', self.extra_args)
        
        # 展开 %VAR%
        def percent_replacer(m):
            vn = m[1].lower()
            return self.env.get(vn, m[0])
        text = re.sub(r'%(\w+)%', percent_replacer, text)
        
        # 展开 !VAR!（延迟展开）
        if self._delayed_expansion:
            def bang_replacer(m):
                vn = m[1].lower()
                return self.env.get(vn, m[0])
            text = re.sub(r'!(\w+)!', bang_replacer, text)
        
        return text
    
    def _resolve_path(self, path: str) -> str:
        if os.path.isabs(path):
            return path
        return os.path.join(self.rom_dir, path).replace('\\', '/')
    
    def _mock_file_exists(self, path: str) -> bool:
        """Mock 文件系统"""
        clean = re.sub(r'%[^%]+%', '', path)
        basename = os.path.basename(clean).lower()
        
        # 优先检查真实文件系统
        if os.path.exists(path):
            return True
        
        # 槽位专属文件（含 _a / _b）必须真实存在
        slot_pattern = r'_[ab]\.(img|bin|elf)$'
        if re.search(slot_pattern, basename):
            return False  # 没有真实文件，视为不存在
        
        # 镜像文件默认视为存在
        if any(clean.lower().endswith(ext) for ext in IMAGE_EXTS):
            return True
        if basename in SPECIAL_FILES:
            return True
        return False
    
    def _load_script(self, filename: str) -> Optional[List[NormalizedCmd]]:
        if filename in self._script_cache:
            return self._script_cache[filename]
        
        full_path = self._resolve_path(filename)
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            from .normalizer import BatNormalizer
            normalizer = BatNormalizer()
            cmds = normalizer.normalize(content)
            self._script_cache[filename] = cmds
            return cmds
        except FileNotFoundError:
            return None
    
    def _resolve_collection(self, loop_type: str, collection: str, flags: Dict) -> List[str]:
        """解析 for 循环的集合"""
        collection = collection.strip().strip('(').strip(')').strip()
        
        if loop_type == '' or loop_type == '/f':
            items = self._split_collection(collection)
            # 通配符展开
            expanded = []
            import glob
            for item in items:
                # 清理：去引号 + 反斜杠转正斜杠
                clean = item.strip('"').strip("'").replace('\\', '/')
                if '*' in clean or '?' in clean:
                    matches = glob.glob(clean)
                    if matches:
                        expanded.extend(sorted(matches))
                    else:
                        expanded.append(clean)
                else:
                    expanded.append(clean)
            return expanded
        
        elif loop_type == '/l':
            parts = [p.strip() for p in collection.split(',')]
            if len(parts) >= 3:
                try:
                    start, step, end = int(parts[0]), int(parts[1]), int(parts[2])
                    result = []
                    i = start
                    count = 0
                    while i <= end and count < 1000:
                        result.append(str(i))
                        i += step
                        count += 1
                    return result
                except ValueError:
                    return []
            return []
        
        elif loop_type == '/r':
            parts = collection.split()
            root = self.rom_dir if len(parts) > 1 and not parts[0].startswith('*') else '.'
            pattern = parts[-1] if len(parts) > 1 else parts[0]
            matches = []
            try:
                for dirpath, _, filenames in os.walk(os.path.join(self.rom_dir, root)):
                    for fn in filenames:
                        if fnmatch.fnmatch(fn, pattern):
                            matches.append(os.path.join(dirpath, fn))
            except Exception:
                pass
            return matches[:500]
        
        return []
    
    def _split_collection(self, text: str) -> List[str]:
        """分割集合"""
        items = []
        cur = ''
        in_q = False
        for ch in text:
            if ch == '"':
                in_q = not in_q
            elif ch in (' ', '\t') and not in_q:
                if cur:
                    items.append(cur)
                    cur = ''
            else:
                cur += ch
        if cur:
            items.append(cur)
        return items
    
    def _make_frame(self, cmds: List[NormalizedCmd], pc: int = 0) -> CallFrame:
        label_index = {}
        for i, cmd in enumerate(cmds):
            if cmd.type == 'LABEL':
                label_index[cmd.args[0].lower()] = i
        return CallFrame(cmds=cmds, pc=pc, label_index=label_index)
    
    def _smart_split(self, line: str) -> List[str]:
        parts = []
        cur = ''
        in_q = False
        for ch in line:
            if ch == '"':
                in_q = not in_q
                continue
            if ch in (' ', '\t') and not in_q:
                if cur:
                    parts.append(cur)
                    cur = ''
            else:
                cur += ch
        if cur:
            parts.append(cur)
        return parts