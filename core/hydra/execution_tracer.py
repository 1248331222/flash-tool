# -*- coding: utf-8 -*-
# flash_tool/core/hydra/execution_tracer.py
"""
Hydra — 执行追踪器
====================
通过真实执行 SH 脚本捕获 fastboot 命令（第三层混合架构）。

核心职责：
  1. 将 SH 脚本通过 termux-usb 或 adb 转发执行
  2. 使用脚本插桩（instrumentation）拦截 fastboot 命令
  3. 收集实际执行的命令序列
  4. 处理执行超时和错误

设计思路：
  对于静态分析无法完全解析的复杂脚本，采用「轻量级插桩执行」方式：
  - 在脚本执行前注入环境变量（劫持 fastboot 为记录器）
  - 真正的 fastboot 暂不执行，只记录命令
  - 适用于需要运行时决策的脚本（!VAR! 延迟扩展等）

注意事项：
  - 只支持 SH 脚本（BAT 需要 Windows 环境，暂不支持）
  - 需要 Termux 中的 bash 环境
  - 真实执行有风险，建议在沙箱环境使用
"""

import os
import re
import subprocess
import tempfile
import json
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from .types import HydraStep


# ============================================================
# ExecutionTracer — 执行追踪器
# ============================================================

class ExecutionTracer:
    """
    执行追踪器 — 真实执行 SH 脚本捕获 fastboot 命令

    用法:
        tracer = ExecutionTracer()
        steps = tracer.trace(script_path="/path/to/flash.sh", rom_dir="/path/to/rom")

    原理：
      通过劫持 fastboot 命令为包装器（记录命令 + 模拟返回），
      让脚本在沙箱中「假执行」，从而捕获所有实际运行的 fastboot 命令。
    """

    def __init__(self):
        self._timeout: int = 300  # 默认超时 5 分钟
        self._captured_commands: List[str] = []

    def trace(
        self,
        script_path: str,
        rom_dir: str = "",
        timeout: int = 300,
    ) -> List[HydraStep]:
        """
        追踪执行 SH 脚本，捕获 fastboot 命令

        Args:
            script_path: 脚本文件的完整路径
            rom_dir: ROM 包根目录（作为工作目录）
            timeout: 执行超时时间（秒）

        Returns:
            HydraStep 列表
        """
        self._timeout = timeout
        self._captured_commands = []

        if not os.path.isfile(script_path):
            return []

        script_dir = os.path.dirname(script_path)
        work_dir = rom_dir or script_dir

        # 创建插桩包装脚本
        instrumented_script = self._create_instrumented_script(
            script_path, script_dir, work_dir
        )

        if instrumented_script is None:
            return []

        # 写入临时文件并执行
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.sh', delete=False, dir=work_dir
            ) as f:
                f.write(instrumented_script)
                temp_script = f.name

            os.chmod(temp_script, 0o755)

            # 执行
            result = subprocess.run(
                ['bash', temp_script],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )

            # 从输出中提取捕获的命令
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line.startswith('[HYDRA_CAPTURE]'):
                    cmd = line[len('[HYDRA_CAPTURE]'):].strip()
                    self._captured_commands.append(cmd)

            # 清理临时文件
            try:
                os.unlink(temp_script)
            except OSError:
                pass

        except subprocess.TimeoutExpired:
            print(f"[Hydra] 执行追踪超时 ({self._timeout}s)")
        except Exception as e:
            print(f"[Hydra] 执行追踪错误: {e}")
        finally:
            try:
                os.unlink(temp_script)
            except (OSError, NameError, UnboundLocalError):
                pass

        # 转换为 HydraStep
        steps = self._commands_to_steps(self._captured_commands)
        return steps

    def trace_script_content(
        self,
        content: str,
        work_dir: str = "",
        timeout: int = 300,
    ) -> List[HydraStep]:
        """
        追踪脚本内容（无需文件系统上的脚本文件）

        Args:
            content: 脚本内容字符串
            work_dir: 工作目录
            timeout: 执行超时

        Returns:
            HydraStep 列表
        """
        self._timeout = timeout
        self._captured_commands = []

        # 插入插桩代码
        instrumented = []
        instrumented.append('#!/data/data/com.termux/files/usr/bin/bash')
        instrumented.append(self._make_fastboot_wrapper())
        instrumented.append(content)

        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.sh', delete=False, dir=work_dir or '/tmp'
            ) as f:
                f.write('\n'.join(instrumented))
                temp_script = f.name

            os.chmod(temp_script, 0o755)

            result = subprocess.run(
                ['bash', temp_script],
                cwd=work_dir or os.getcwd(),
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )

            for line in result.stdout.split('\n'):
                line = line.strip()
                if line.startswith('[HYDRA_CAPTURE]'):
                    cmd = line[len('[HYDRA_CAPTURE]'):].strip()
                    self._captured_commands.append(cmd)

            try:
                os.unlink(temp_script)
            except OSError:
                pass

        except subprocess.TimeoutExpired:
            print(f"[Hydra] 内容追踪超时 ({self._timeout}s)")
        except Exception as e:
            print(f"[Hydra] 内容追踪错误: {e}")

        return self._commands_to_steps(self._captured_commands)

    # ----------------------------------------------------------
    # 插桩脚本生成
    # ----------------------------------------------------------

    def _make_fastboot_wrapper(self) -> str:
        """
        生成 fastboot 命令包装函数

        BAT: 劫持 %FASTBOOT% 或 fastboot.exe 调用
        SH:  劫持 $FASTBOOT 或 fastboot 命令

        注入到脚本的 PATH 中，使脚本调用我们的包装器而不是真正的 fastboot
        """
        return r'''
# ===== Hydra 插桩：劫持 fastboot 命令 =====
__hydra_captured_file=""

# 创建一个假的 fastboot 脚本，记录所有命令
__hydra_fake_fastboot() {
    echo "[HYDRA_CAPTURE] fastboot $*" >&2
    # 不真正执行，返回成功
    return 0
}

# 劫持 $FASTBOOT 变量
FASTBOOT="__hydra_fake_fastboot"
export FASTBOOT

# 将包装器加入 PATH 最前面
__hydra_wrapper_dir="$(mktemp -d)"
cat > "$__hydra_wrapper_dir/fastboot" << 'WRAPPER'
#!/data/data/com.termux/files/usr/bin/bash
echo "[HYDRA_CAPTURE] fastboot $*" >&2
exit 0
WRAPPER
chmod +x "$__hydra_wrapper_dir/fastboot"
export PATH="$__hydra_wrapper_dir:$PATH"

# 清理函数
__hydra_cleanup() {
    rm -rf "$__hydra_wrapper_dir" 2>/dev/null || true
}
trap __hydra_cleanup EXIT
# ===== Hydra 插桩结束 =====
'''

    def _create_instrumented_script(
        self,
        script_path: str,
        script_dir: str,
        work_dir: str,
    ) -> Optional[str]:
        """
        创建插桩后的脚本

        1. 读取原始脚本
        2. 在开头注入 fastboot 包装器
        3. 返回插桩后的完整脚本内容
        """
        if not os.path.isfile(script_path):
            return None

        try:
            with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            return None

        lines = content.split('\n')

        # 去掉原有 shebang
        if lines and lines[0].startswith('#!'):
            lines = lines[1:]

        # 构建插桩脚本
        instrumented = []
        instrumented.append('#!/data/data/com.termux/files/usr/bin/bash')
        instrumented.append(self._make_fastboot_wrapper())
        instrumented.append('')
        instrumented.append(f'# === 原始脚本: {os.path.basename(script_path)} ===')
        instrumented.append(f'cd "{work_dir}"')
        instrumented.append('')

        # 保留原有注释和代码
        instrumented.extend(lines)

        # 捕获脚本退出前的 fastboot 包装器清理
        instrumented.append('__hydra_cleanup')

        return '\n'.join(instrumented)

    # ----------------------------------------------------------
    # 结果转换
    # ----------------------------------------------------------

    def _commands_to_steps(self, commands: List[str]) -> List[HydraStep]:
        """
        将捕获的命令行转换为 HydraStep 列表
        """
        from .command_extractor import CommandExtractor

        extractor = CommandExtractor()
        steps = []

        for cmd in commands:
            # 去掉 "fastboot " 前缀，只保留尾部
            tail = re.sub(r'^fastboot\s+', '', cmd, flags=re.I).strip()
            if not tail:
                continue

            # 用 CommandExtractor 的快速方法解析
            if not extractor._is_fastboot_line(cmd):
                continue

            step_dict = extractor._cmd_parser._parser_parse(tail, cmd)
            if step_dict is None:
                continue

            step = HydraStep(
                type=step_dict.get("type", "unknown"),
                part=step_dict.get("part", ""),
                fileName=step_dict.get("fileName", ""),
                params=step_dict.get("params", ""),
                raw=cmd,
                risk=step_dict.get("risk", "B"),
                dynamic=False,  # 真实执行捕获的，不是动态的
            )
            steps.append(step)

        # 评估风险
        for step in steps:
            step_dict = {
                "type": step.type, "part": step.part,
                "params": step.params, "raw": step.raw,
            }
            step.risk = extractor._cmd_parser._parser_risk(step_dict)

        return steps

    @property
    def captured_commands(self) -> List[str]:
        """获取捕获的命令行列表"""
        return list(self._captured_commands)


__all__ = ["ExecutionTracer"]