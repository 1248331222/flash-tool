# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/script_type_detector.py
"""
Hydra — 脚本类型自动识别
=========================
不依赖文件名后缀，通过内容特征识别 BAT / SH / PowerShell 脚本。

识别依据：
  BAT：@echo off, setlocal, goto :label, :label, %%var, !var!, %~1
  SH：  #!/bin/bash, #!/bin/sh, $VAR, ${VAR}, $(cmd), for var in, if [ ]
  PowerShell: #requires, param(), $var =, Write-Host, Get-ChildItem

优先级：内容头检测 > 关键字评分 > 文件名后缀兜底
"""

import re
from typing import Tuple


# ---------- 加权评分规则 ----------
# (正则模式, 分值, 说明)
_BAT_PATTERNS = [
    (r'@echo\s+off',                30,  '典型的 BAT 头部'),
    (r'setlocal\s+(enabledelayedexpansion|disabledelayedexpansion)', 30, 'BAT setlocal'),
    (r'%\w+%',                      15,  'BAT 变量引用 %VAR%'),
    (r'%%\w+',                      15,  'BAT for 循环变量 %%i'),
    (r'!\w+!',                      10,  '延迟展开变量 !var!'),
    (r'%~\d+',                      10,  'BAT 参数引用 %~1'),
    (r':\w+',                       2,   'BAT 标签 :label（单行首）'),
    (r'goto\s+\w+',                 20,  'goto 跳转'),
    (r'call\s+:\w+',                20,  'call 子过程'),
    (r'chcp\s+\d+',                 15,  '字符集设置'),
    (r'title\s+',                   5,   'BAT title'),
    (r'assoc\s*=',                  5,   'BAT 关联'),
    (r'ftype\s+',                   5,   'BAT 文件类型'),
    (r'if\s+(not\s+)?(exist|errorlevel|defined)\b', 15, 'BAT if 条件'),
    (r'for\s+%%\w+',               15,  'BAT for 循环'),
    (r'for\s+/\w+\s+%%',           20,  'BAT for /L /F /R'),
    (r'\bshift\b',                  10,  'BAT shift'),
]

_SH_PATTERNS = [
    (r'#!/usr/bin/env\s+bash',      50,  'bash shebang'),
    (r'#!/bin/bash',                50,  'bash shebang'),
    (r'#!/bin/sh',                  50,  'sh shebang'),
    (r'\$\{[a-zA-Z_][a-zA-Z0-9_]*\}', 20, 'SH 变量 ${VAR}'),
    (r'\$\([^)]+\)',                15,  'SH 命令替换 $(cmd)'),
    (r'\$\w+',                      10,  'SH 变量 $VAR'),
    (r'\\\$',                       3,   'SH 转义'),
    (r'\[\s+[^\]]+\s+\]',          8,   'SH test 表达式'),
    (r'if\s+\[',                    15,  'SH if ['),
    (r'elif\s+\[',                  15,  'SH elif ['),
    (r'for\s+\w+\s+in\s+',         15,  'SH for in'),
    (r'while\s+read\s+',           15,  'SH while read'),
    (r'\bcase\s+\w+\s+in\b',       15,  'SH case'),
    (r'\bdone\b',                   8,   'SH done（循环结束）'),
    (r'\bfi\b',                     8,   'SH fi（if 结束）'),
    (r'\besac\b',                   5,   'SH esac（case 结束）'),
    (r'export\s+\w+=',             10,  'SH export 变量'),
    (r'local\s+\w+=',              10,  'SH local 变量'),
    (r"'[^']*'",                    2,   'SH 单引号字符串'),
    (r'`[^`]+`',                    5,   'SH 反引号命令替换'),
    (r'\|[|&]',                     3,   'SH 管道/逻辑'),
    (r'>>\s*/',                     5,   'SH 重定向到路径'),
    (r'>\s*/',                      5,   'SH 重定向到路径'),
    (r'\bexit\s+\d+\b',            5,   'SH exit 码'),
    (r'read\s+(-[a-z]+\s+)?\w+',   10,  'SH read 输入'),
    (r'\\\n',                       1,   'SH 行延续'),
]

_PS_PATTERNS = [
    (r'#requires\s',               30,  'PowerShell 需求声明'),
    (r'param\s*\(',                20,  'PowerShell 参数'),
    (r'Write-(Host|Output|Error|Warning|Verbose|Debug|Information)', 20, 'PowerShell 输出'),
    (r'Get-ChildItem|Get-Item|Get-Content|Set-Content', 15, 'PowerShell cmdlet'),
    (r'\$[a-zA-Z_]\s*=',           8,   'PowerShell 变量赋值'),
    (r'\$\w+\.\w+',                5,   'PowerShell 属性访问'),
    (r'PowerShell\s*\[',           20,  'PowerShell 属性'),
    (r'\[[A-Z][a-zA-Z0-9.]+]',    5,   'PowerShell 类型字面量'),
    (r'foreach\s*\(',              10,  'PowerShell foreach'),
    (r'Where-Object|Select-Object|ForEach-Object', 15, 'PowerShell 管道 cmdlet'),
    (r'EndOfStatement',            5,   'PowerShell AST 模式'),
    (r'\bnew-object\b',            10,  'PowerShell New-Object'),
]

# 行首标签检测（BAT 特有的 :label 行）
_LABEL_LINE_RE = re.compile(r'^\s*:\w+', re.MULTILINE)


def detect_script_type(content: str, filename: str = "") -> str:
    """
    自动识别脚本类型。

    返回 "bat" | "sh" | "ps" | "unknown"
    优先级：内容头部检测 > 评分 > 文件名后缀

    参数:
        content: 脚本内容
        filename: 可选，文件名（含后缀），用于兜底
    """
    if not content or not content.strip():
        return _fallback_by_filename(filename)

    scores = {"bat": 0, "sh": 0, "ps": 0}

    # 1. Shebang 检测（最高优先级）
    first_line = content.strip().split('\n')[0].strip()
    if first_line.startswith('#!'):
        if 'bash' in first_line or 'sh' in first_line or 'zsh' in first_line or 'dash' in first_line:
            return 'sh'
        # 其他 shebang 不强行判定

    # 2. BAT 头部特征
    head = content[:500].lower()
    if '@echo off' in head:
        scores['bat'] += 40
    if 'setlocal' in head:
        scores['bat'] += 25
    if 'chcp' in head:
        scores['bat'] += 15
    if 'enabledelayedexpansion' in head:
        scores['bat'] += 20
    if '!tmp!' in head or '!cd!' in head or '!errorlevel!' in head:
        scores['bat'] += 15

    # 3. SH 头部特征
    if '#!/bin/bash' in head or '#!/usr/bin/env bash' in head or '#!/bin/sh' in head:
        scores['sh'] += 50
    if '#!/usr/bin/env' in head and not head.startswith('#!/usr/bin/env bash'):
        # 通用 python/perl 等不判定为 sh
        pass

    # 4. 关键字评分
    for pattern, score, _desc in _BAT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            scores['bat'] += score

    for pattern, score, _desc in _SH_PATTERNS:
        if re.search(pattern, content):
            scores['sh'] += score

    for pattern, score, _desc in _PS_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            scores['ps'] += score

    # 5. BAT 标签行评分（避免在 SH 的 case 分支中被误判）
    label_count = len(_LABEL_LINE_RE.findall(content))
    if label_count >= 2:
        scores['bat'] += min(label_count * 5, 30)

    # 6. SH 独有检测：单行被 [ ] 包围的 test 表达式
    bracket_test_count = len(re.findall(r'^\s*\[[^\]]+\]\s*$', content, re.MULTILINE))
    if bracket_test_count >= 1:
        scores['sh'] += min(bracket_test_count * 5, 20)

    # 7. 最终判断
    # 如果某个类型得分显著高于其他（>= 总分 60%），则判定为该类型
    total = max(scores['bat'], scores['sh'], scores['ps'])
    if total <= 0:
        return _fallback_by_filename(filename)

    # 分差判定（最高分 >= 次高分 * 2 且 >= 30 分）
    sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
    best_type, best_score = sorted_scores[0]
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0

    if best_score >= second_score * 2 and best_score >= 20:
        return best_type

    # 如果分差不够，走文件名兜底
    return _fallback_by_filename(filename)


def _fallback_by_filename(filename: str) -> str:
    """通过文件名后缀兜底"""
    if not filename:
        return "unknown"
    name = filename.lower()
    if name.endswith('.bat') or name.endswith('.cmd'):
        return 'bat'
    if name.endswith('.sh'):
        return 'sh'
    if name.endswith('.ps1'):
        return 'ps'
    return 'unknown'


def detect_script_type_with_confidence(content: str, filename: str = "") -> Tuple[str, str]:
    """
    识别脚本类型并附可信度。

    返回 (type, confidence) 其中 confidence 为 certain / probable / uncertain

    参数:
        content: 脚本内容
        filename: 可选，文件名用于兜底
    """
    if not content or not content.strip():
        ft = _fallback_by_filename(filename)
        return (ft, "uncertain" if ft == "unknown" else "probable")

    first_line = content.strip().split('\n')[0].strip()
    if '#!/bin/bash' in first_line or '#!/usr/bin/env bash' in first_line:
        return ('sh', 'certain')
    if '#!/bin/sh' in first_line:
        return ('sh', 'certain')
    if first_line.startswith('#!') and 'python' in first_line:
        return ('unknown', 'uncertain')

    head = content[:500].lower()
    if '@echo off' in head and 'setlocal' in head:
        # 典型 BAT 头部：极高置信度
        return ('bat', 'certain')

    # 用评分系统
    r = detect_script_type(content, filename)
    if r == 'unknown':
        return (r, 'uncertain')

    # 计算得分比例判断可信度
    scores = {"bat": 0, "sh": 0, "ps": 0}
    for pattern, score, _desc in _BAT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            scores['bat'] += score
    for pattern, score, _desc in _SH_PATTERNS:
        if re.search(pattern, content):
            scores['sh'] += score
    for pattern, score, _desc in _PS_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            scores['ps'] += score

    sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
    best_score = sorted_scores[0][1] if sorted_scores else 0
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0

    if best_score >= 40 and best_score >= second_score * 3:
        return (r, 'certain')
    if best_score >= 20 and best_score >= second_score * 2:
        return (r, 'probable')
    return (r, 'uncertain')


__all__ = ["detect_script_type", "detect_script_type_with_confidence"]