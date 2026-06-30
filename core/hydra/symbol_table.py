# -*- coding: utf-8 -*-
# flash_tool/core/hydra/symbol_table.py
"""
Hydra — 变量符号表
====================
追踪变量赋值与引用，支持 BAT 和 SH 两种脚本语言。

核心功能：
  1. 记录变量名 → 值的映射（支持 BAT 的大小写不敏感）
  2. 记录变量引用关系（谁引用了谁）
  3. 记录变量定义位置（行号）
  4. 支持变量展开（%VAR%、!VAR!、$VAR、${VAR}）
  5. 追踪延迟扩展变量（setlocal enabledelayedexpansion 后的 !VAR!）

BAT 变量特点：
  - 大小写不敏感（统一用 UPPER 存储）
  - %VAR% 静态展开
  - !VAR! 延迟扩展（运行时展开）
  - %VAR:old=new% 字符串替换
  - %VAR:~start,len% 切片
  - %~dp0 等路径修饰符

SH 变量特点：
  - 大小写敏感
  - $VAR / ${VAR} 引用
  - $((expr)) 算术展开
  - $(cmd) 命令替换（暂不执行）
"""

import re
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field


# ============================================================
# SymbolEntry — 符号表条目
# ============================================================

@dataclass
class SymbolEntry:
    """单个变量的元信息"""
    name: str               # 变量名
    value: str = ""         # 当前值
    is_defined: bool = True # 是否已定义
    line_no: int = 0        # 定义行号
    script_type: str = "bat"  # 来源脚本类型
    references: Set[int] = field(default_factory=set)  # 被引用的行号集合
    is_delayed: bool = False   # 是否通过延迟扩展定义


# ============================================================
# SymbolTable — 变量符号表
# ============================================================

class SymbolTable:
    """
    变量符号表 — 追踪所有变量赋值与引用

    用法:
        st = SymbolTable()
        st.define("VAR", "value", line_no=10)
        value = st.resolve("%VAR%")
        refs = st.get_references("VAR")
    """

    def __init__(self, script_type: str = "bat"):
        self._entries: Dict[str, SymbolEntry] = {}
        self._script_type = script_type
        self._has_delayed_expansion = False

    def define(
        self,
        name: str,
        value: str = "",
        line_no: int = 0,
        is_delayed: bool = False,
    ) -> "SymbolTable":
        """
        定义/更新变量

        Args:
            name: 变量名
            value: 值
            line_no: 定义行号
            is_delayed: 是否为延迟扩展（BAT !VAR!）

        Returns:
            self（链式调用）
        """
        key = self._normalize(name)
        if key in self._entries:
            self._entries[key].value = value
            self._entries[key].line_no = line_no
            if is_delayed:
                self._entries[key].is_delayed = True
        else:
            self._entries[key] = SymbolEntry(
                name=key,
                value=value,
                line_no=line_no,
                script_type=self._script_type,
                is_delayed=is_delayed,
            )
        return self

    def undefine(self, name: str) -> "SymbolTable":
        """
        删除变量定义

        Args:
            name: 变量名
        """
        key = self._normalize(name)
        self._entries.pop(key, None)
        return self

    def get(self, name: str, default: str = None) -> Optional[str]:
        """获取变量值"""
        key = self._normalize(name)
        entry = self._entries.get(key)
        if entry and entry.is_defined:
            return entry.value
        return default

    def get_entry(self, name: str) -> Optional[SymbolEntry]:
        """获取变量完整条目"""
        key = self._normalize(name)
        return self._entries.get(key)

    def is_defined(self, name: str) -> bool:
        """检查变量是否已定义"""
        key = self._normalize(name)
        return key in self._entries and self._entries[key].is_defined

    def add_reference(self, name: str, line_no: int):
        """记录变量被引用的行号"""
        key = self._normalize(name)
        if key in self._entries:
            self._entries[key].references.add(line_no)

    def get_references(self, name: str) -> Set[int]:
        """获取变量被引用的行号集合"""
        key = self._normalize(name)
        entry = self._entries.get(key)
        return entry.references if entry else set()

    def get_all(self) -> Dict[str, str]:
        """获取所有变量名→值的映射"""
        return {
            k: v.value
            for k, v in self._entries.items()
            if v.is_defined
        }

    def get_undefined(self, names: Set[str]) -> List[str]:
        """从一组变量名中找出未定义的"""
        return [n for n in names if not self.is_defined(n)]

    def mark_delayed_expansion(self, enabled: bool = True):
        """标记脚本是否启用延迟扩展"""
        self._has_delayed_expansion = enabled

    def has_delayed_expansion(self) -> bool:
        """脚本是否启用了延迟扩展"""
        return self._has_delayed_expansion

    def merge(self, other: "SymbolTable"):
        """合并另一个符号表"""
        for key, entry in other._entries.items():
            if key not in self._entries:
                self._entries[key] = entry
            else:
                # 保留最新的定义
                if entry.line_no > self._entries[key].line_no:
                    self._entries[key] = entry
        return self

    def reset(self):
        """清空所有条目"""
        self._entries.clear()
        self._has_delayed_expansion = False

    # ----------------------------------------------------------
    # 变量展开
    # ----------------------------------------------------------

    def resolve(self, text: str, line_no: int = 0) -> str:
        """
        展开文本中的所有变量引用

        支持：
          BAT: %VAR%、!VAR!、%VAR:old=new%、%VAR:~start,len%、%~dp0
          SH:  $VAR、${VAR}

        Args:
            text: 包含变量引用的文本
            line_no: 当前行号（用于记录引用关系）

        Returns:
            展开后的文本
        """
        if self._script_type == "bat":
            return self._resolve_bat(text, line_no)
        else:
            return self._resolve_sh(text, line_no)

    def _resolve_bat(self, text: str, line_no: int = 0) -> str:
        """BAT 变量展开（增强版：延迟扩展写回符号表）"""
        prev = None
        result = text
        for _ in range(10):
            prev = result
            # !VAR! 延迟扩展 — 展开后写回符号表（模拟 setlocal 运行时行为）
            if self._has_delayed_expansion:
                def _delayed_repl(m):
                    vname = m.group(1)
                    resolved = self._resolve_ref(vname, line_no)
                    # 如果值是纯文本且不含未展开变量，写回到符号表
                    if '%' not in resolved and '!' not in resolved:
                        self.define(vname, resolved, line_no=line_no, is_delayed=True)
                    return resolved
                result = re.sub(r'!(\w+)!', _delayed_repl, result)
            # %VAR% 静态展开
            result = re.sub(
                r'%(\w+)%',
                lambda m: self._resolve_ref(m.group(1), line_no),
                result,
            )
            if result == prev:
                break

        # 3. 字符串替换 %VAR:old=new%
        def _repl_sub(m):
            vn = m.group(1)
            old = m.group(2)
            new_val = m.group(3)
            val = self.get(vn, m.group(0))
            return val.replace(old, new_val)

        result = re.sub(r'%(\w+):([^=]+)=(.+?)%', _repl_sub, result)

        # 4. 字符串切片 %VAR:~start,length%
        def _slice_sub(m):
            vn = m.group(1)
            s = int(m.group(2))
            l = m.group(3)
            val = self.get(vn, m.group(0))
            return val[s:s + int(l)] if l else val[s:]

        result = re.sub(r'%(\w+):~(\d+),(\d+)?%', _slice_sub, result)

        return result

    def _resolve_sh(self, text: str, line_no: int = 0) -> str:
        """SH 变量展开（支持 ${VAR:-default} 默认值语法，多轮递归展开）"""
        prev = None
        result = text
        for _ in range(10):
            prev = result

            # 1. ${VAR:-default} 和 ${VAR:=default} 默认值语法
            def _repl_default(m):
                vname = m.group(1)
                default_val = m.group(2)
                if self.is_defined(vname):
                    return self._resolve_ref(vname, line_no)
                else:
                    return default_val

            result = re.sub(r'\$\{(\w+):[=-](.+?)\}', _repl_default, result)

            # 2. ${VAR:+alt} 替代值语法
            result = re.sub(
                r'\$\{(\w+):\+(.+?)\}',
                lambda m: self._resolve_ref(m.group(1), line_no) if self.is_defined(m.group(1)) else '',
                result,
            )

            # 3. ${VAR} 语法
            result = re.sub(
                r'\$\{(\w+)\}',
                lambda m: self._resolve_ref(m.group(1), line_no),
                result,
            )

            # 4. $VAR
            result = re.sub(
                r'\$(\w+)',
                lambda m: self._resolve_ref(m.group(1), line_no),
                result,
            )

            if result == prev:
                break

        return result

    def _resolve_ref(self, name: str, line_no: int) -> str:
        """解析单个变量引用"""
        if line_no > 0:
            self.add_reference(name, line_no)

        value = self.get(name, None)
        if value is not None:
            return value
        # 未定义的变量：
        if self._script_type == "sh":
            return ""  # SH 中未定义变量展开为空字符串
        return f"%{name}%"  # BAT 中未定义变量保留原样

    def _normalize(self, name: str) -> str:
        """统一变量名格式"""
        if self._script_type == "bat":
            return name.upper()
        return name

    def __repr__(self) -> str:
        items = ', '.join(f"{k}={v.value}" for k, v in self._entries.items() if v.is_defined)
        return f"SymbolTable({{{items}}})"


__all__ = ["SymbolTable", "SymbolEntry"]