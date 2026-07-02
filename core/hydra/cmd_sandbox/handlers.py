# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/cmd_sandbox/handlers.py
"""
Hydra — Win CMD 沙箱：内置命令处理器

14E-1 第一版支持：
  - echo
  - set
  - cd / chdir
  - pushd / popd
  - fastboot / adb（捕获 + mock 输出）
  - exit /b
  - goto :eof
"""

import os
import re as re_mod
from typing import Optional

from .runtime import WinCmdRuntime
from .vfs import VirtualFileSystem
from .result import CommandResult
from .parser import strip_redirection


def handle_echo(runtime: WinCmdRuntime, vfs: VirtualFileSystem,
                text: str) -> CommandResult:
    """echo 命令——模拟输出到 stdout。"""
    resolved = runtime.resolve(text).strip().strip('"')
    return CommandResult(stdout=[resolved])


def handle_set(runtime: WinCmdRuntime, vfs: VirtualFileSystem,
               line: str) -> CommandResult:
    """set VAR=value 命令。"""
    m = __import__('re').match(
        r'^"?([A-Za-z0-9_]+)"?=(.*)$',
        line.strip(), __import__('re').I
    )
    if m:
        key = m.group(1)
        value = m.group(2).strip().strip('"')
        resolved = runtime.resolve(value)
        runtime.set_var(key, resolved)
    return CommandResult()


def handle_cd(runtime: WinCmdRuntime, vfs: VirtualFileSystem,
              target: str) -> CommandResult:
    """cd / chdir 命令。"""
    target = runtime.resolve(target).strip().strip('"').strip("'")
    target = target.replace('\\\\', '/').replace('\\', '/')
    if not os.path.isabs(target):
        target = os.path.join(runtime.cwd, target)
    if vfs.exists(target) and vfs.is_dir(target):
        runtime.cwd = target
        runtime.set_var('CD', target)
        vfs.set_cwd(target)
        return CommandResult()
    return CommandResult(errorlevel=1, stderr=[f"cd: {target}: directory not found"])


def handle_pushd(runtime: WinCmdRuntime, vfs: VirtualFileSystem,
                 target: str) -> CommandResult:
    """pushd 命令。"""
    target = runtime.resolve(target).strip().strip('"').strip("'")
    target = target.replace('\\\\', '/').replace('\\', '/')
    if not os.path.isabs(target):
        target = os.path.join(runtime.cwd, target)
    runtime.dir_stack.append(runtime.cwd)
    if vfs.exists(target) and vfs.is_dir(target):
        runtime.cwd = target
        runtime.set_var('CD', target)
        vfs.set_cwd(target)
        return CommandResult()
    return CommandResult(errorlevel=1, stderr=[f"pushd: {target}: directory not found"])


def handle_popd(runtime: WinCmdRuntime, vfs: VirtualFileSystem) -> CommandResult:
    """popd 命令。"""
    if runtime.dir_stack:
        runtime.cwd = runtime.dir_stack.pop()
        runtime.set_var('CD', runtime.cwd)
        vfs.set_cwd(runtime.cwd)
        return CommandResult()
    return CommandResult(errorlevel=1, stderr=["popd: directory stack empty"])


def handle_exit_b(runtime: WinCmdRuntime, vfs: VirtualFileSystem,
                  code_str: str = "") -> CommandResult:
    """exit /b [code] 命令。"""
    if code_str:
        try:
            code = int(runtime.resolve(code_str).strip())
        except ValueError:
            code = 0
    else:
        code = runtime.errorlevel
    runtime.set_errorlevel(code)
    return CommandResult(errorlevel=code)


# ============================================================
# 14E-2 文件命令处理器
# ============================================================

def handle_dir(runtime: WinCmdRuntime, vfs: VirtualFileSystem,
               args: str) -> CommandResult:
    """dir [path] 命令——列出目录内容。"""
    args = runtime.resolve(args).strip().strip('"').strip("'")
    target = args if args else "."
    target = target.replace('\\\\', '/').replace('\\', '/')
    if not os.path.isabs(target):
        target = os.path.join(runtime.cwd, target)

    if not vfs.exists(target):
        return CommandResult(errorlevel=1,
                             stdout=[f" File Not Found: {target}"])
    if vfs.is_file(target):
        return CommandResult(stdout=[f" Directory of {os.path.dirname(target)}",
                                      f"    1 File(s)  {os.path.basename(target)}"])
    # 目录
    items = vfs.listdir(target)
    stdout = [f" Directory of {target}"]
    for item in items:
        full = os.path.join(target, item)
        if vfs.is_dir(full):
            stdout.append(f"    <DIR>    {item}")
        else:
            stdout.append(f"             {item}")
    stdout.append(f"    {len(items)} File(s)")
    return CommandResult(stdout=stdout)


def handle_where(runtime: WinCmdRuntime, vfs: VirtualFileSystem,
                 args: str) -> CommandResult:
    """where [tool] 命令——查找可执行文件路径。"""
    tool = runtime.resolve(args).strip().strip('"').strip("'")
    if not tool:
        return CommandResult(errorlevel=1, stderr=["ERROR: The syntax of this command is:"])
    tool_lower = tool.lower()
    # 已知刷机工具
    known_tools = {
        "fastboot": runtime.get_var("FASTBOOT", "fastboot"),
        "adb": runtime.get_var("ADB", "adb"),
        "mfastboot": "mfastboot",
    }
    path = known_tools.get(tool_lower)
    if path:
        return CommandResult(stdout=[path])
    return CommandResult(errorlevel=1,
                         stdout=[f"INFO: Could not find files for the given pattern(s)."])


def handle_copy(runtime: WinCmdRuntime, vfs: VirtualFileSystem,
                args: str) -> CommandResult:
    """copy src dst——复制文件。"""
    args = runtime.resolve(args)
    # 解析 src 和 dst
    # 支持 copy src dst 或 copy /Y src dst
    args = re_mod.sub(r'^/\w+\s+', '', args).strip()
    parts = args.rsplit(None, 1)
    if len(parts) < 2:
        return CommandResult(errorlevel=1, stderr=["The syntax of the command is incorrect."])
    src, dst = parts[0].strip('"'), parts[1].strip('"')
    ok = vfs.copy(src, dst)
    return CommandResult(
        errorlevel=0 if ok else 1,
        stdout=[f"        1 file(s) copied."] if ok else [f"        0 file(s) copied."],
    )


def handle_move(runtime: WinCmdRuntime, vfs: VirtualFileSystem,
                args: str) -> CommandResult:
    """move src dst——移动文件。"""
    args = runtime.resolve(args)
    args = re_mod.sub(r'^/\w+\s+', '', args).strip()
    parts = args.rsplit(None, 1)
    if len(parts) < 2:
        return CommandResult(errorlevel=1, stderr=["The syntax of the command is incorrect."])
    src, dst = parts[0].strip('"'), parts[1].strip('"')
    ok = vfs.move(src, dst)
    return CommandResult(
        errorlevel=0 if ok else 1,
        stdout=[f"        1 file(s) moved."] if ok else [f"        0 file(s) moved."],
    )


def handle_del(runtime: WinCmdRuntime, vfs: VirtualFileSystem,
               args: str) -> CommandResult:
    """del / erase 文件名——删除文件。"""
    args = runtime.resolve(args).strip().strip('"').strip("'")
    args = re_mod.sub(r'^/\w+\s+', '', args).strip()
    if not args:
        return CommandResult(errorlevel=1, stderr=["The syntax of the command is incorrect."])
    ok = vfs.delete(args)
    return CommandResult(
        errorlevel=0 if ok else 1,
        stdout=[f"        1 file(s) deleted."] if ok else [f"        0 file(s) deleted."],
    )


def handle_mkdir(runtime: WinCmdRuntime, vfs: VirtualFileSystem,
                 args: str) -> CommandResult:
    """mkdir / md 目录名——创建目录。"""
    args = runtime.resolve(args).strip().strip('"').strip("'")
    if not args:
        return CommandResult(errorlevel=1, stderr=["The syntax of the command is incorrect."])
    ok = vfs.mkdir(args)
    return CommandResult(errorlevel=0 if ok else 1)


def handle_rmdir(runtime: WinCmdRuntime, vfs: VirtualFileSystem,
                 args: str) -> CommandResult:
    """rmdir / rd 目录名——删除目录。"""
    args = runtime.resolve(args).strip().strip('"').strip("'")
    args = re_mod.sub(r'^/\w+\s+', '', args).strip()
    if not args:
        return CommandResult(errorlevel=1, stderr=["The syntax of the command is incorrect."])
    ok = vfs.delete(args)
    return CommandResult(errorlevel=0 if ok else 1)


def handle_type(runtime: WinCmdRuntime, vfs: VirtualFileSystem,
                args: str) -> CommandResult:
    """type 文件名——输出文件内容。"""
    args = runtime.resolve(args).strip().strip('"').strip("'")
    if not args:
        return CommandResult(errorlevel=1, stderr=["The syntax of the command is incorrect."])
    content = vfs.read_text(args)
    if content is None:
        return CommandResult(errorlevel=1,
                             stderr=[f"The system cannot find the file specified."])
    return CommandResult(stdout=content.splitlines())


# ============================================================
# 14E-3 findstr 命令
# ============================================================

def handle_findstr(runtime: WinCmdRuntime, vfs: VirtualFileSystem,
                   args: str) -> CommandResult:
    """
    findstr 简化版。

    支持：
      findstr keyword file
      findstr /i keyword file
      findstr /r pattern file
      findstr keyword（从 stdin 匹配）
    """
    args = runtime.resolve(args).strip()
    case_sensitive = True
    use_regex = False

    # 解析开关
    while args.startswith('/'):
        m = re_mod.match(r'^/(\w+)\s*', args)
        if m:
            opt = m.group(1).lower()
            if opt == 'i':
                case_sensitive = False
            elif opt == 'r':
                use_regex = True
            elif opt in ('v', 'n', 'x', 'c', 'b'):
                pass  # 暂不支持
            args = args[m.end():]
        else:
            break

    args = args.strip()
    if not args:
        return CommandResult(errorlevel=1, stderr=["FINDSTR: Insufficient arguments"])

    # 分割 keyword 和 file
    parts = args.rsplit(None, 1) if ' ' in args else [args]
    if len(parts) == 2:
        keyword = parts[0].strip().strip('"').strip("'")
        filepath = parts[1].strip().strip('"').strip("'")
    else:
        keyword = parts[0].strip().strip('"').strip("'")
        filepath = None

    # 从文件或 stdin 读取行
    lines = []
    if filepath:
        content = vfs.read_text(filepath)
        if content is None:
            return CommandResult(errorlevel=1,
                                 stderr=[f"FINDSTR: Cannot open {filepath}"])
        lines = content.splitlines()
    else:
        # 从 stdout 匹配（调用方提供 stdin）
        lines = runtime.last_stdout if hasattr(runtime, 'last_stdout') and runtime.last_stdout else []

    matched = []
    for line in lines:
        if use_regex:
            flags = 0 if case_sensitive else re_mod.IGNORECASE
            if re_mod.search(keyword, line, flags):
                matched.append(line)
        else:
            if case_sensitive:
                if keyword in line:
                    matched.append(line)
            else:
                if keyword.lower() in line.lower():
                    matched.append(line)

    if matched:
        return CommandResult(errorlevel=0, stdout=matched)
    return CommandResult(errorlevel=1, stdout=[])


def handle_fastboot(runtime: WinCmdRuntime, vfs: VirtualFileSystem,
                    cmd: str) -> CommandResult:
    """fastboot / adb 命令——mock 捕获。"""
    resolved = runtime.resolve(cmd)
    runtime.capture(resolved)
    lower = resolved.lower()
    stdout = ["<mock>"]
    errorlevel = 0

    # 模拟常见 fastboot 检查命令的输出
    if "devices" in lower:
        stdout = ["FAKEDEVICE    fastboot"]
    elif "getvar" in lower:
        if "product" in lower:
            stdout = ["product: hydra_mock"]
        elif "current-slot" in lower:
            stdout = ["current-slot: a"]
        elif "max-download-size" in lower:
            stdout = ["max-download-size: 1073741824"]
        else:
            stdout = ["<getvar mock>"]
        stdout.append("finished. total time: 0.001s")
    elif "reboot" in lower:
        errorlevel = 0
        stdout = ["Rebooting..."]
    elif "flash" in lower:
        # 刷入命令——检查 VFS 中是否有对应镜像文件
        # 提取最后一个参数作为文件路径
        parts = resolved.split()
        if len(parts) >= 3:
            img_path = parts[-1]
            if not vfs.exists(img_path):
                stdout = [f"<mock flash {parts[-2]}: no image file, continuing anyway>"]
            else:
                stdout = [f"<mock flash {parts[-2]}: OK>"]
        else:
            stdout = ["<mock flash>"]
    else:
        stdout = ["<mock fastboot>"]

    return CommandResult(
        errorlevel=errorlevel,
        stdout=stdout,
        captured=resolved,
        is_fastboot=True,
    )


# ============================================================
# 派发表：name -> handler function
# ============================================================

BUILTIN_HANDLERS = {
    "echo": handle_echo,
    "set": handle_set,
    "cd": handle_cd,
    "chdir": handle_cd,
    "pushd": handle_pushd,
    "popd": handle_popd,
    "exit": handle_exit_b,
    "dir": handle_dir,
    "where": handle_where,
    "copy": handle_copy,
    "xcopy": handle_copy,
    "move": handle_move,
    "del": handle_del,
    "erase": handle_del,
    "mkdir": handle_mkdir,
    "md": handle_mkdir,
    "rmdir": handle_rmdir,
    "rd": handle_rmdir,
    "type": handle_type,
    "findstr": handle_findstr,
}


def dispatch_builtin(runtime: WinCmdRuntime, vfs: VirtualFileSystem,
                     command: str) -> Optional[CommandResult]:
    """
    分发内置命令。
    如果 command 是内置命令，返回 CommandResult。
    否则返回 None（交给外部命令处理）。
    """
    lower = command.strip().lower()
    parts = lower.split(None, 1)
    if not parts:
        return None
    cmd_name = parts[0]
    cmd_args = parts[1] if len(parts) > 1 else ""

    handler = BUILTIN_HANDLERS.get(cmd_name)
    if handler:
        return handler(runtime, vfs, cmd_args)
    return None


def handle_external(runtime: WinCmdRuntime, vfs: VirtualFileSystem,
                    command: str) -> CommandResult:
    """处理外部命令——检查是否是 fastboot/adb。"""
    lower = command.strip().lower()
    if lower.startswith("fastboot") or lower.startswith("adb"):
        return handle_fastboot(runtime, vfs, command)
    # 未知外部命令，忽略（模拟找不到命令）
    return CommandResult(stdout=[f"'{command}' is not recognized as an internal or external command"])


__all__ = [
    "BUILTIN_HANDLERS", "dispatch_builtin", "handle_external",
    "handle_echo", "handle_set", "handle_cd", "handle_pushd",
    "handle_popd", "handle_exit_b", "handle_fastboot",
    "handle_dir", "handle_where", "handle_copy", "handle_move",
    "handle_del", "handle_mkdir", "handle_rmdir", "handle_type",
    "handle_findstr",
]