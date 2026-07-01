# -*- coding: utf-8 -*-
# flash_tool/core/hydra/path_resolver.py
"""
Hydra — 统一路径解析器
========================
集中处理刷机脚本中所有路径解析逻辑。

处理的路径形式：
  BAT:
    images\boot.img
    .\images\boot.img
    ..\images\boot.img
    %~dp0images\boot.img
    %CD%\images\boot.img
    %~dp0..\images\boot.img
    %~f0\images\boot.img
    d:\images\boot.img
    
  SH:
    images/boot.img
    ./images/boot.img
    ../images/boot.img
    $DIR/images/boot.img
    ${DIR}/images/boot.img
    "$DIR/images/boot.img"
    'images/boot.img'
    ~/images/boot.img

输出：
  PathResolution 数据类
    original:      原始路径
    normalized:    标准化路径（/ 分隔，无变量引用）
    resolved:      拼接 script_dir 或 rom_dir 后的完整路径
    exists:        文件是否存在
    source:        来源描述（rom_dir / script_dir / absolute / unknown）

用法：
    from core.hydra.path_resolver import PathResolver
    
    resolver = PathResolver(script_dir="/rom", rom_dir="/rom")
    pr = resolver.resolve("images\\boot.img")
    pr.exists    # True/False
    pr.resolved  # "/rom/images/boot.img"
    pr.source    # "rom_dir"
"""

import os
import re
from typing import Optional, Set
from dataclasses import dataclass, field


# ============================================================
# BAT 路径变量正则
# ============================================================

# %~dp0 — 脚本目录（带尾部分隔符）
_BAT_DP0 = re.compile(r'%~dp0', re.IGNORECASE)
# %~f0 — 脚本完整路径
_BAT_F0 = re.compile(r'%~f0', re.IGNORECASE)
# %~df0 — 脚本所在驱动器
_BAT_DF0 = re.compile(r'%~df0', re.IGNORECASE)
# %CD% — 当前目录
_BAT_CD = re.compile(r'%CD%', re.IGNORECASE)
# %~dpnx0 — 脚本目录+文件名+扩展名（简化：类比 %~dp0）
_BAT_DPNX0 = re.compile(r'%~dpnx0', re.IGNORECASE)
# %~d0 — 脚本所在驱动器
_BAT_D0 = re.compile(r'%~d0', re.IGNORECASE)
# %~nx0 — 脚本文件名+扩展名
_BAT_NX0 = re.compile(r'%~nx0', re.IGNORECASE)

# 通用 %VAR% 变量（已知的路径类变量）
_BAT_PATH_VAR = re.compile(r'%([^%]+)%')

# SH $DIR / ${DIR} / $HOME
_SH_DIR_VAR = re.compile(r'\$\{?(\w+)\}?')
_SH_HOME = re.compile(r'^~/')


# ============================================================
# 已知路径变量名
# ============================================================

BAT_KNOWN_PATH_VARS = {
    'CD', 'TEMP', 'TMP', 'WINDIR', 'SYSTEMROOT',
    'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH',
}

SH_KNOWN_PATH_VARS = {
    'HOME', 'DIR', 'SCRIPT_DIR', 'ROM_DIR',
    'PWD', 'OLDPWD', 'TMPDIR', 'ANDROID_PRODUCT_OUT',
}


# ============================================================
# PathResolution — 路径解析结果
# ============================================================

@dataclass
class PathResolution:
    """单条路径的解析结果"""
    original: str = ""          # 原始路径文本
    normalized: str = ""        # 标准化路径（/ 分隔，无变量）
    resolved: str = ""          # 完整解析路径
    exists: bool = False        # 文件是否存在
    source: str = "unknown"     # 来源: rom_dir / script_dir / absolute / unknown
    note: str = ""              # 说明


# ============================================================
# PathResolver — 路径解析器
# ============================================================

class PathResolver:
    """
    统一路径解析器。

    Args:
        script_dir: 脚本所在目录
        rom_dir: ROM 根目录
        cwd: 当前工作目录（默认 script_dir）
        known_vars: 已知变量名集合（只用于源判断，实际展开靠 Environment）
    """

    def __init__(
        self,
        script_dir: str = "",
        rom_dir: str = "",
        cwd: str = "",
        known_vars: dict = None,
    ):
        self.script_dir = self._norm_dir(script_dir)
        self.rom_dir = self._norm_dir(rom_dir)
        self.cwd = self._norm_dir(cwd) if cwd else self.script_dir
        self.known_vars = dict(known_vars) if known_vars else {}

    @staticmethod
    def _norm_dir(d: str) -> str:
        """标准化目录路径"""
        if not d:
            return ""
        d = d.replace('\\', '/')
        # 去掉尾部 /
        if d.endswith('/') and len(d) > 1:
            d = d[:-1]
        return d

    @staticmethod
    def normalize(path: str) -> str:
        """路径标准化：\\ → /，去掉多余 ./"""
        if not path:
            return path
        # 转正斜杠
        path = path.replace('\\', '/')
        # 去掉多余重复的 /（保留开头的双 //）
        parts = path.split('/')
        cleaned = []
        for p in parts:
            if p == '' or p == '.':
                if not cleaned:
                    # 开头的空（表示 / 开头）或 . 保留
                    pass
                else:
                    continue
            elif p == '..':
                if cleaned and cleaned[-1] != '..':
                    cleaned.pop()
                else:
                    cleaned.append(p)
            else:
                cleaned.append(p)
        result = '/'.join(cleaned)
        # 处理以 .. 开头的情况
        if path.startswith('/'):
            result = '/' + result
        elif path.startswith('./'):
            result = result
        elif path.startswith('../'):
            result = result
        return result

    def resolve_bat_path_vars(self, path: str) -> str:
        """展开 BAT 路径变量（%~dp0, %CD% 等）"""
        if not path:
            return path

        script_dir = self.script_dir or "."
        # 确保目录有尾部 /
        sd_trailing = script_dir + '/' if not script_dir.endswith('/') else script_dir

        # %~dp0 → script_dir + /
        path = _BAT_DP0.sub(sd_trailing, path)
        # %~dpnx0 → script_dir + /（简化处理）
        path = _BAT_DPNX0.sub(sd_trailing, path)
        # %~f0 → script_dir + 脚本名（近似处理）
        path = _BAT_F0.sub(os.path.join(script_dir, 'script.bat').replace('\\', '/'), path)
        # %CD% → cwd
        path = _BAT_CD.sub(self.cwd.replace('\\', '/'), path)
        # %~df0 → 驱动器（如果没有则留空）
        path = _BAT_DF0.sub('', path)
        # %~d0 → 驱动器
        path = _BAT_D0.sub('', path)
        # %~nx0 → 脚本名称
        path = _BAT_NX0.sub('script.bat', path)

        # 已知变量展开
        def _expand_known(m):
            varname = m.group(1)
            val = self.known_vars.get(varname, '')
            if val:
                return val.replace('\\', '/')
            if varname in BAT_KNOWN_PATH_VARS:
                return m.group(0)  # 保留原样，交给 Environment
            return m.group(0)
        path = _BAT_PATH_VAR.sub(_expand_known, path)

        return path

    def resolve_sh_path_vars(self, path: str) -> str:
        """展开 SH 路径变量（$DIR, ${DIR}, ~/ 等）"""
        if not path:
            return path

        script_dir = self.script_dir or "."

        # ~/ → HOME（或 script_dir）
        if path.startswith('~/'):
            home = self.known_vars.get('HOME', script_dir)
            path = home.replace('\\', '/') + '/' + path[2:]

        # $DIR / ${DIR}
        def _expand_sh_var(m):
            varname = m.group(1)
            val = self.known_vars.get(varname, '')
            if val:
                return val.replace('\\', '/')
            if varname in SH_KNOWN_PATH_VARS:
                return m.group(0)  # 保留
            return m.group(0)
        path = _SH_DIR_VAR.sub(_expand_sh_var, path)

        return path

    def resolve(
        self,
        path: str,
        script_type: str = "bat",
        cwd: str = None,
    ) -> PathResolution:
        """
        统一路径解析入口。

        Args:
            path: 原始路径
            script_type: "bat" | "sh"（影响变量展开规则）
            cwd: 当前工作目录（可选，覆盖 self.cwd）

        Returns:
            PathResolution
        """
        if not path:
            return PathResolution(original=path, note="空路径")

        original = path
        cwd = self._norm_dir(cwd) if cwd else self.cwd

        # 1. 变量展开
        if script_type == "bat":
            expanded = self.resolve_bat_path_vars(path)
        else:
            expanded = self.resolve_sh_path_vars(path)

        # 2. 标准化
        normalized = self.normalize(expanded)

        # 3. 尝试解析完整路径
        resolved = None
        source = "unknown"

        if os.path.isabs(normalized):
            resolved = normalized
            source = "absolute"
        else:
            # 尝试 cwd
            if cwd and normalized:
                candidate = os.path.join(cwd, normalized).replace('\\', '/')
                if os.path.exists(candidate) or os.path.isdir(candidate):
                    resolved = candidate
                    source = "cwd"

            # 尝试 script_dir
            if resolved is None and self.script_dir and normalized:
                candidate = os.path.join(self.script_dir, normalized).replace('\\', '/')
                if os.path.exists(candidate) or os.path.isdir(candidate):
                    resolved = candidate
                    source = "script_dir"

            # 尝试 rom_dir
            if resolved is None and self.rom_dir and normalized:
                candidate = os.path.join(self.rom_dir, normalized).replace('\\', '/')
                if os.path.exists(candidate) or os.path.isdir(candidate):
                    resolved = candidate
                    source = "rom_dir"

            # fallback 到 script_dir + normalized
            if resolved is None and self.script_dir:
                resolved = os.path.join(self.script_dir, normalized).replace('\\', '/')
                source = "script_dir_fallback"
            elif resolved is None:
                resolved = normalized
                source = "unknown"

        exists = os.path.exists(resolved) if resolved else False

        return PathResolution(
            original=original,
            normalized=normalized,
            resolved=resolved or normalized,
            exists=exists,
            source=source,
        )

    def resolve_image(
        self,
        fileName: str,
        script_type: str = "bat",
    ) -> PathResolution:
        """专门解析镜像文件路径"""
        pr = self.resolve(fileName, script_type=script_type)

        # 如果未找到，再尝试直接基于文件名在 rom_dir 中搜索
        if not pr.exists and self.rom_dir and fileName:
            base = os.path.basename(fileName.replace('\\', '/'))
            if base != fileName:
                candidate = os.path.join(self.rom_dir, base).replace('\\', '/')
                if os.path.exists(candidate):
                    return PathResolution(
                        original=fileName,
                        normalized=base,
                        resolved=candidate,
                        exists=True,
                        source="rom_dir_basename",
                    )
        return pr


__all__ = [
    "PathResolver",
    "PathResolution",
    "BAT_KNOWN_PATH_VARS",
    "SH_KNOWN_PATH_VARS",
]