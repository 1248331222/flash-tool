# -*- coding: utf-8 -*-
# flash_tool/core/hydra/cmd_sandbox/vfs.py
"""
Hydra — Win CMD 沙箱：虚拟文件系统

混合 VFS 设计：
- 真实目录只读映射（ROM 目录、脚本目录）
- 沙箱 tmp 目录支持写入
"""

import os
import glob as glob_mod
import tempfile
import shutil
from typing import List, Optional


class VirtualFileSystem:
    """混合虚拟文件系统

    路径解析顺序：
      1. 绝对路径 → 直接使用
      2. cwd 相对路径 → 优先 script_dir，再 rom_dir，最后沙箱 tmp
      3. 写入操作（write/copy/move/mkdir/delete）统一写入沙箱 tmp
    """

    def __init__(self, script_dir: str = "", rom_dir: str = "", cwd: str = ""):
        self.script_dir = script_dir or os.getcwd()
        self.rom_dir = rom_dir or ""
        self._cwd = cwd or self.script_dir

        # 沙箱临时目录，可写
        self._sandbox_tmp = tempfile.mkdtemp(prefix="hydra_vfs_")
        self._sandbox_files: set = set()  # 记录沙箱内文件

    def set_cwd(self, cwd: str):
        self._cwd = cwd

    def _norm(self, path: str) -> str:
        """归一化路径：转正斜杠、去掉多余部分。"""
        path = str(path).replace('\\\\', '/').replace('\\', '/')
        # 去掉多余 ./ 和 ../
        return os.path.normpath(path)

    def _resolve_read(self, path: str) -> str:
        """解析读取路径：优先真实文件，其次沙箱。"""
        p = self._norm(path)
        if os.path.isabs(p):
            return p

        candidates = []

        # 1. 相对 cwd
        candidates.append(os.path.join(self._cwd, p))

        # 2. 相对 script_dir
        if self._cwd != self.script_dir:
            candidates.append(os.path.join(self.script_dir, p))

        # 3. 相对 rom_dir
        if self.rom_dir:
            candidates.append(os.path.join(self.rom_dir, p))

        # 4. 沙箱 tmp
        candidates.append(os.path.join(self._sandbox_tmp, p))

        for c in candidates:
            if os.path.exists(c):
                return c
        # 全部不存在则返回沙箱路径（写入操作时使用）
        return candidates[-1]

    def _resolve_write(self, path: str) -> str:
        """解析写入路径：统一写入沙箱 tmp。"""
        p = self._norm(path)
        if os.path.isabs(p):
            return p
        return os.path.join(self._sandbox_tmp, p)

    def exists(self, path: str) -> bool:
        real = self._resolve_read(path)
        return os.path.exists(real)

    def is_file(self, path: str) -> bool:
        real = self._resolve_read(path)
        return os.path.isfile(real)

    def is_dir(self, path: str) -> bool:
        real = self._resolve_read(path)
        return os.path.isdir(real)

    def listdir(self, path: str) -> List[str]:
        real = self._resolve_read(path)
        if not os.path.isdir(real):
            return []
        try:
            return os.listdir(real)
        except PermissionError:
            return []

    def read_text(self, path: str) -> Optional[str]:
        real = self._resolve_read(path)
        try:
            with open(real, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return None

    def write_text(self, path: str, content: str) -> bool:
        p = self._resolve_write(path)
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8') as f:
                f.write(content)
            self._sandbox_files.add(p)
            return True
        except Exception:
            return False

    def copy(self, src: str, dst: str) -> bool:
        src_real = self._resolve_read(src)
        dst_real = self._resolve_write(dst)
        try:
            os.makedirs(os.path.dirname(dst_real), exist_ok=True)
            shutil.copy2(src_real, dst_real)
            self._sandbox_files.add(dst_real)
            return True
        except Exception:
            return False

    def move(self, src: str, dst: str) -> bool:
        src_real = self._resolve_read(src)
        dst_real = self._resolve_write(dst)
        try:
            os.makedirs(os.path.dirname(dst_real), exist_ok=True)
            shutil.move(src_real, dst_real)
            return True
        except Exception:
            return False

    def delete(self, path: str) -> bool:
        real = self._resolve_read(path)
        try:
            if os.path.isfile(real):
                os.remove(real)
            elif os.path.isdir(real):
                shutil.rmtree(real)
            return True
        except Exception:
            return False

    def mkdir(self, path: str) -> bool:
        real = self._resolve_write(path)
        try:
            os.makedirs(real, exist_ok=True)
            return True
        except Exception:
            return False

    def glob(self, pattern: str) -> List[str]:
        """支持 * ? 通配符，在真实目录 + 沙箱中搜索。"""
        results = glob_mod.glob(self._resolve_read(pattern))
        return [os.path.relpath(p, self.script_dir) for p in results]

    def cleanup(self):
        """清除沙箱临时目录"""
        shutil.rmtree(self._sandbox_tmp, ignore_errors=True)

    def __del__(self):
        self.cleanup()


__all__ = ["VirtualFileSystem"]