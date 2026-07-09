"""
BAT 指令归一化器
把 BAT 语法（set/if/goto/call/for/exit）归一化为中间表示 NormalizedCmd
"""
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class NormalizedCmd:
    """归一化后的指令"""
    type: str         # SET / IF_EXIST / IF_EQ / IF_ERRORLEVEL / GOTO / LABEL / CALL / FOR / EXEC / EXIT
    args: list = field(default_factory=list)
    flags: dict = field(default_factory=dict)
    raw: str = ""
    lineno: int = 0


class BatNormalizer:
    """BAT 指令归一化器"""
    
    IGNORE_PATTERNS = [
        r'^\s*@?(echo|rem|::|cls|title|color|chcp|cd\b)',
        r'^\s*@?echo\b',
        r'^\s*$',
        r'^\s*@?\s*$',
        r'^\s*\)',           # 闭合括号单独一行
        r'^\s*@?pause\b',    # pause 可在执行器中收集为步骤，此处不回显
    ]
    
    def normalize(self, content: str) -> List[NormalizedCmd]:
        """将 BAT 文本归一化为指令列表"""
        lines = content.split('\n')
        cmds = []
        i = 0
        while i < len(lines):
            lineno = i + 1
            raw = lines[i]
            line = raw.strip()
            
            # 跳过空行/注释
            if self._should_skip(line):
                i += 1
                continue
            
            # 去掉行首 @
            if line.startswith('@'):
                line = line[1:].strip()
            
            # 检测 if / for 多行块
            if self._is_block_start(line):
                block_end = self._find_block_end(lines, i)
                block_lines = lines[i:block_end + 1]
                block_cmds = self._parse_block(block_lines, i + 1)
                cmds.extend(block_cmds)
                i = block_end + 1
                continue
            
            cmd = self._parse_line(line, raw, lineno)
            if cmd:
                cmds.append(cmd)
            i += 1
        
        return cmds
    
    def _is_block_start(self, line: str) -> bool:
        """检测行是否以 ( 结尾表示多行块起始"""
        stripped = line
        if stripped.startswith('@'):
            stripped = stripped[1:].strip()
        
        # 必须行尾是 ( 
        if not stripped.rstrip().endswith('('):
            return False
        
        # 排除 if not exist ... ( ?? 不，全保留：|| ( 和 if exist ( 都应作为块
        # 因为 normalizer 不能丢弃块内内容（可能有 echo/exit 需要标记）
        # 特殊处理：|| ( ... ) → 块无动作，块内 exit 被标记但不阻主流程
        
        # 检查行尾 ( 前面最近的关键词
        before_paren = stripped.rstrip()[:-1].rstrip()  # 去掉末尾 (
        if before_paren.endswith('do'):
            return True  # for ... do ( → 多行块
        if before_paren.endswith(')'):
            return False  # for ... in (...) → 可能是单行括号
        
        # || ( 和 if exist ( 都是合法的多行块
        return True
    
    def _find_block_end(self, lines: list, start: int) -> int:
        """找到多行块的闭合 ) 位置
        
        策略：
        1. 首行中，只计最后一个 ( 之后的深度
        2. 后续行全量计括号差值
        3. depth 归零时返回
        """
        first_line = lines[start]
        # 找到最后一个 ( 的位置
        last_open = first_line.rfind('(')
        if last_open < 0:
            return start
        
        # 最后一个 ( 之后的深度（通常为 1）
        after_last = first_line[last_open + 1:]
        depth = 1 + after_last.count('(') - after_last.count(')')
        
        for i in range(start + 1, len(lines)):
            line = lines[i]
            depth += line.count('(') - line.count(')')
            if depth == 0:
                return i
        
        return start
    
    def _parse_block(self, block_lines: list, base_lineno: int) -> List[NormalizedCmd]:
        """解析多行块，返回归一化指令列表"""
        # 第一行形如: if exist "X" ( 或 for %%i in (X) do (
        header = block_lines[0].strip()
        if header.startswith('@'):
            header = header[1:].strip()
        
        # 提取块类型和参数
        header_cmd = self._parse_line(header, block_lines[0], base_lineno)
        
        # 检测 else 分支
        # 块内指令：排除首行(header)和末行(闭合))
        body_lines = []
        else_lines = []
        in_else = False
        for raw in block_lines[1:-1]:
            line = raw.strip()
            if not line:
                continue
            # 检测 else 分支：支持 ) else ( 和 else 开头
            if re.match(r'\)?\s*else', line, re.IGNORECASE):
                in_else = True
                # 提取 else 后面的内容（去掉括号）
                else_part = re.sub(r'(?i)^\)?\s*else\s*\(?\s*', '', line).strip()
                if else_part:
                    else_lines.append(else_part)
                continue
            if in_else:
                else_lines.append(line)
            else:
                body_lines.append(line)
        
        # 对块内指令递归归一化
        body_text = '\n'.join(body_lines)
        body_cmds = self.normalize(body_text) if body_text.strip() else []
        
        else_cmds = []
        if else_lines:
            else_text = '\n'.join(else_lines)
            else_cmds = self.normalize(else_text)
        
        if header_cmd and header_cmd.type in ('IF_EXIST', 'IF_EQ', 'IF_ERRORLEVEL', 'FOR'):
            if else_cmds:
                block_cmd = NormalizedCmd(
                    'BLOCK_ELSE',
                    args=[header_cmd, body_cmds, else_cmds],
                    raw=block_lines[0],
                    lineno=base_lineno,
                )
            else:
                block_cmd = NormalizedCmd(
                    'BLOCK',
                    args=[header_cmd, body_cmds],
                    raw=block_lines[0],
                    lineno=base_lineno,
                )
            return [block_cmd]
        
        # 头部不是标准 if/for（如 || ( ... ) 条件执行块）
        # 分离 || 或 && 前的命令作为独立 EXEC，块内容包起来但不引入 EXIT 阻断
        pre_cmds = []
        if header_cmd:
            # 尝试提取 || / && 前的命令
            raw_header = block_lines[0].strip()
            m_split = re.split(r'\s*\|\||\s*&&\s*', raw_header, maxsplit=1)
            if len(m_split) > 1:
                # 前面部分作为独立命令
                pre_line = m_split[0].strip()
                pre_parsed = self._parse_line(pre_line, pre_line, base_lineno)
                if pre_parsed:
                    pre_cmds.append(pre_parsed)
        # 块内 EXIT 替换为 NOP 防止阻断主流程
        sanitized = []
        for c in body_cmds:
            if c.type == 'EXIT':
                sanitized.append(NormalizedCmd('SET', args=['_block_exit', '1'], raw=c.raw, lineno=c.lineno))
            else:
                sanitized.append(c)
        return pre_cmds + sanitized
    
    def _should_skip(self, line: str) -> bool:
        for p in self.IGNORE_PATTERNS:
            if re.match(p, line):
                return True
        return False
    
    def _parse_line(self, line: str, raw: str, lineno: int) -> Optional[NormalizedCmd]:
        """解析单行 BAT 指令"""
        # :LABEL
        m = re.match(r'^:(\w+)', line)
        if m:
            return NormalizedCmd('LABEL', args=[m[1]], raw=raw, lineno=lineno)
        
        # set "VAR=VAL"
        m = re.match(r'(?i)set\s+"?(\w+)=(.*)', line)
        if m:
            val = m[2].strip().strip('"')
            return NormalizedCmd('SET', args=[m[1], val], raw=raw, lineno=lineno)
        
        # set /p var=prompt — 交互输入点
        m = re.match(r'(?i)set\s+/p\s+(\w+)\s*=\s*(.*)', line)
        if m:
            var_name = m.group(1)
            prompt = m.group(2).strip().strip('"').strip("'")
            return NormalizedCmd('INTERACTIVE', args=[var_name, prompt], raw=raw, lineno=lineno)
        
        # if exist / if not exist
        m = re.match(r'(?i)if\s+(not\s+)?exist\s+"?(.+?)"?\s+(.+)', line)
        if m:
            not_exist = bool(m[1])
            path = m[2].strip('"')
            action = m[3].strip()
            return NormalizedCmd('IF_EXIST', args=[not_exist, path, action], raw=raw, lineno=lineno)
        
        # if /i "!VAR!"=="val" (支持延迟展开变量)
        m = re.match(r'(?i)if\s+(/i\s+)?(?:not\s+)?["\']?!(\w+)!["\']?\s*==\s*["\']?(.+?)["\']?\s+(.+)', line)
        if m:
            var_name = m[2]
            expected_val = m[3].strip()
            action = m[4].strip()
            return NormalizedCmd('IF_EQ', args=[var_name, expected_val, action], raw=raw, lineno=lineno)
        
        # if /i "%VAR%"=="val"
        m = re.match(r'(?i)if\s+(/i\s+)?["\']?%(\w+)%["\']?\s*==\s*["\']?(.+?)["\']?\s+(.+)', line)
        if m:
            var_name = m[2]
            expected_val = m[3].strip()
            action = m[4].strip()
            return NormalizedCmd('IF_EQ', args=[var_name, expected_val, action], raw=raw, lineno=lineno)
        
        # if "%VAR%"=="val" (无 /i 版)
        m = re.match(r'(?i)if\s+"?%(\w+)%"?\s*==\s*"?(\w+)"?\s+(.+)', line)
        if m:
            return NormalizedCmd('IF_EQ', args=[m[1], m[2], m[3].strip()], raw=raw, lineno=lineno)
        
        # if errorlevel N
        m = re.match(r'(?i)if\s+(not\s+)?errorlevel\s+(\d+)\s+(.+)', line)
        if m:
            return NormalizedCmd('IF_ERRORLEVEL', args=[bool(m[1]), int(m[2]), m[3].strip()], raw=raw, lineno=lineno)
        
        # goto :LABEL / goto LABEL
        m = re.match(r'(?i)goto\s+:?(\w+)', line)
        if m:
            return NormalizedCmd('GOTO', args=[m[1]], raw=raw, lineno=lineno)
        
        # call :SUB (内部标签)
        m = re.match(r'(?i)call\s+:(\w+)', line)
        if m:
            return NormalizedCmd('CALL', args=[f':{m[1]}'], raw=raw, lineno=lineno)
        
        # call script.bat (外部脚本)
        m = re.match(r'(?i)call\s+(\S+\.bat)', line)
        if m:
            return NormalizedCmd('CALL', args=[m[1]], raw=raw, lineno=lineno)
        
        # for %%i in (...) do ...
        m = re.match(
            r'(?i)for\s+(/f\s+("[^"]*"\s+)?|/l\s+|/r\s+)?'
            r'%%(\w)\s+in\s+\((.+?)\)\s+do\s+(.+)',
            line
        )
        if m:
            # m.groups() = (loop_type, for_f_flags, var, collection, body)
            groups = m.groups()
            loop_type = (groups[0] or '').strip()
            var_name = groups[2]  # 原始变量名如 p, i
            collection = groups[3].strip()
            body = groups[4].strip()
            flags = {}
            if loop_type == '/f' and groups[1]:
                flags = self._parse_for_f_flags(groups[1].strip('"'))
            return NormalizedCmd('FOR', args=[loop_type, var_name, collection, body],
                                flags=flags, raw=raw, lineno=lineno)
        
        # exit /b
        if re.match(r'(?i)exit(\s+/b)?', line):
            return NormalizedCmd('EXIT', raw=raw, lineno=lineno)
        
        # 执行命令行 — 包含 fastboot / adb / 或变量引用的变体
        if re.match(r'(?i)(fastboot|%fastboot%|adb|%adb%)', line):
            clean = line.replace('%FASTBOOT%', 'fastboot').replace('%fastboot%', 'fastboot')
            clean = clean.replace('%ADB%', 'adb').replace('%adb%', 'adb')
            parts = self._smart_split(clean)
            return NormalizedCmd('EXEC', args=parts, raw=raw, lineno=lineno)
        
        # 兜底：任何未被其他类型匹配的行，都作为可能的外部命令
        # 排除注释/echo/pause/title/cls/color/chcp/cd/timeout 等
        first_word = line.split()[0] if line.split() else ''
        if not re.match(r'^@?(rem|::|echo|pause|title|cls|color|chcp|cd|timeout)\b', line, re.I):
            parts = self._smart_split(line)
            return NormalizedCmd('EXEC', args=parts, raw=raw, lineno=lineno)
        
        return None
    
    def _parse_for_f_flags(self, opts: str) -> Dict:
        """解析 for /f 选项"""
        flags = {}
        for part in re.findall(r'(\w+)=([^ ]+)', opts):
            flags[part[0]] = part[1]
        return flags
    
    def _smart_split(self, line: str) -> List[str]:
        """智能分割命令行，保留引号包裹的参数"""
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