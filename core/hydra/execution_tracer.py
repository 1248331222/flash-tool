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

        # 预先清理全局捕获文件
        global_cap = '/tmp/.hydra_global_capture'
        try:
            if os.path.exists(global_cap):
                os.unlink(global_cap)
        except OSError:
            pass

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

            # 从 stdout 和 stderr 中提取捕获的命令
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line.startswith('[HYDRA_CAPTURE]'):
                    cmd = line[len('[HYDRA_CAPTURE]'):].strip()
                    self._captured_commands.append(cmd)
            # 也检查 stderr（包装器用 stderr 输出时用）
            for line in result.stderr.split('\n'):
                line = line.strip()
                if line.startswith('[HYDRA_CAPTURE]'):
                    cmd = line[len('[HYDRA_CAPTURE]'):].strip()
                    self._captured_commands.append(cmd)

            # 从全局捕获文件中读取（抗重定向方案）
            try:
                if os.path.exists(global_cap):
                    with open(global_cap, 'r') as cf:
                        for cl in cf:
                            cl = cl.strip()
                            if cl.startswith('[HYDRA_CAPTURE]'):
                                cmd = cl[len('[HYDRA_CAPTURE]'):].strip()
                                if cmd:
                                    self._captured_commands.append(cmd)
                    os.unlink(global_cap)
            except Exception:
                pass

            # 清理临时文件
            try:
                os.unlink(temp_script)
            except OSError:
                pass

        except subprocess.TimeoutExpired:
            pass  # 超时是正常业务行为（脚本含交互或设备等待），不影响已有结果
        except Exception as e:
            print(f"[Hydra] 执行追踪错误: {e}")
        finally:
            try:
                os.unlink(temp_script)
            except (OSError, NameError, UnboundLocalError):
                pass
            # 清理工作目录中的日志文件（脚本执行产生的 flash_*.log）
            try:
                import glob
                for log_file in glob.glob(os.path.join(work_dir, 'flash_*.log')):
                    try:
                        os.unlink(log_file)
                    except OSError:
                        pass
            except Exception:
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
        instrumented.append('#!/usr/bin/env bash')
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

            # 也检查 stderr
            for line in result.stderr.split('\n'):
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
        生成 fastboot / adb 命令包装器

        SH:  劫持 $FASTBOOT 或 fastboot 命令
             同时劫持 $ADB 或 adb 命令

        注入到脚本的 PATH 中，使脚本调用我们的包装器而不是真正的工具。
        """
        return r'''
# ===== Hydra 插桩：劫持 fastboot 和 adb 命令 =====

# 捕获列表
__hydra_captured=()

# 创建一个临时目录放包装器
__hydra_wrapper_dir="$(mktemp -d)"

# fastboot 包装器
cat > "$__hydra_wrapper_dir/fastboot" << 'WRAPPER_FASTBOOT'
#!/usr/bin/env bash
# 记录到全局捕获文件
echo "[HYDRA_CAPTURE] fastboot $*" >> /tmp/.hydra_global_capture
# 模拟 fastboot 命令输出，让脚本中的检测逻辑通过
if [[ "$*" == "devices" ]]; then
    echo "hydra_fake_device    fastboot"
elif [[ "$*" == *"reboot"* ]]; then
    :  # reboot 不需要输出
fi
exit 0
WRAPPER_FASTBOOT
chmod +x "$__hydra_wrapper_dir/fastboot"

# adb 包装器
cat > "$__hydra_wrapper_dir/adb" << 'WRAPPER_ADB'
#!/usr/bin/env bash
echo "[HYDRA_CAPTURE] adb $*" >> /tmp/.hydra_global_capture
# adb reboot bootloader 或 adb reboot fastboot 返回成功
if [[ "$*" == *reboot* ]]; then
    exit 0
fi
# 其他 adb 命令也返回成功
exit 0
WRAPPER_ADB
chmod +x "$__hydra_wrapper_dir/adb"

# 将包装器目录加入 PATH 最前面
export PATH="$__hydra_wrapper_dir:$PATH"

# 劫持交互命令，防止卡住
# 禁用内置 read，用 PATH 中的包装器替代
enable -n read 2>/dev/null || true

# 在包装器目录创建空 read
cat > "$__hydra_wrapper_dir/read" << 'WRAPPER_READ'
#!/usr/bin/env bash
exit 0
WRAPPER_READ
chmod +x "$__hydra_wrapper_dir/read"

# sleep 秒返回
cat > "$__hydra_wrapper_dir/sleep" << 'WRAPPER_SLEEP'
#!/usr/bin/env bash
exit 0
WRAPPER_SLEEP
chmod +x "$__hydra_wrapper_dir/sleep"

clear() { return 0; }

# 劫持 $FASTBOOT 和 $ADB 变量
FASTBOOT="$__hydra_wrapper_dir/fastboot"
ADB="$__hydra_wrapper_dir/adb"
export FASTBOOT ADB

# 劫持常见 fastboot 路径变量
FLASHTOOL="$__hydra_wrapper_dir/fastboot"
FASTBOOT_PATH="$__hydra_wrapper_dir/fastboot"
TOOL_PATH="$__hydra_wrapper_dir"
export FLASHTOOL FASTBOOT_PATH TOOL_PATH

# 预设控制变量，让脚本跳过交互菜单进入自动刷写模式
AUTO_FLASH="true"
WIPE_DATA="true"
SKIP_CHECK="true"
NO_REBOOT="true"
export AUTO_FLASH WIPE_DATA SKIP_CHECK NO_REBOOT

# 模拟镜像目录和必要路径，避免脚本因目录不存在而退出
IMG_DIR="/tmp/hydra_fake_images"
mkdir -p "$IMG_DIR"

# 创建假的 .img 文件，让脚本认为镜像存在
# 脚本会检查每个分区的 img 文件是否存在，不存在则跳过
_default_parts="preloader_raw lk apusys audio_dsp boot ccu cdt_engineering dpm dtbo gpueb gz mcf_ota mcupm md1img mvpu_algo pi_img scp spmfw sspm tee vcp vendor_boot vbmeta vbmeta_system vbmeta_vendor"
for _part in $_default_parts; do
    touch "$IMG_DIR/${_part}.img" 2>/dev/null || true
done
# super 镜像单独处理（可能很大）
touch "$IMG_DIR/super.img" 2>/dev/null || true

export IMG_DIR

# ===== 安全隔离：劫持危险命令 =====
# 这些命令在沙箱追踪中不应真正执行，只记录后返回成功
for _dangerous_cmd in rm dd mkfs mount umount curl wget su sudo reboot poweroff shutdown; do
    cat > "$__hydra_wrapper_dir/$_dangerous_cmd" << DANGER_EOF
#!/usr/bin/env bash
echo "[HYDRA_BLOCKED] $_dangerous_cmd \$*" >> /tmp/.hydra_global_capture
exit 0
DANGER_EOF
    chmod +x "$__hydra_wrapper_dir/$_dangerous_cmd"
done
# ===== 安全隔离结束 =====

# 模拟镜像目录和文件
if command -v which &>/dev/null; then
    # 让 type fastboot 返回成功
    type() {
        if [[ "$1" == "fastboot" ]]; then
            echo "fastboot is $__hydra_wrapper_dir/fastboot"
            return 0
        fi
        command type "$@"
    }
    export -f type >/dev/null 2>&1 || true
fi

# 模拟文件存在：让脚本误以为镜像文件存在
if [[ -d /tmp/hydra_fake_files ]]; then
    rm -rf /tmp/hydra_fake_files
fi
mkdir -p /tmp/hydra_fake_files
# 如果脚本在某个目录执行，模拟该目录下的 .img 文件存在
__hydra_workdir="${PWD}"
if [[ -d "$__hydra_workdir" ]]; then
    for f in "$__hydra_workdir"/*.img "$__hydra_workdir"/images/*.img; do
        if [[ -f "$f" ]]; then
            ln -sf "$f" /tmp/hydra_fake_files/ 2>/dev/null || true
        fi
    done
fi

# 清理函数
__hydra_cleanup() {
    command rm -rf "$__hydra_wrapper_dir" /tmp/hydra_fake_files /tmp/hydra_fake_images 2>/dev/null || true
    # 清理脚本产生的日志文件，避免污染工作目录
    if [[ -n "${LOG_FILE:-}" ]]; then
        command rm -f "$LOG_FILE" 2>/dev/null || true
    fi
    command rm -f flash_*.log 2>/dev/null || true
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
        2. 在开头注入 fastboot/adb 包装器
        3. 提取所有函数定义并提前到脚本开头（避免 bash 函数定义前调用失败）
        4. 返回插桩后的完整脚本内容
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

        # 提取所有函数定义
        # 匹配 func_name() { 或 function func_name {
        func_defs = []
        func_ends = []
        i = 0
        brace_depth = 0
        in_func = False
        func_start = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # 检测函数开始：name() { 或 function name {
            if not in_func and re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\s*\(\s*\)\s*\{', stripped):
                in_func = True
                func_start = i
                brace_depth = 1
            elif not in_func and stripped.startswith('function ') and '{' in stripped:
                in_func = True
                func_start = i
                brace_depth = stripped.count('{') - stripped.count('}')
            elif in_func:
                brace_depth += line.count('{') - line.count('}')
                if brace_depth <= 0:
                    in_func = False
                    func_defs.append((func_start, i + 1))

            i += 1

        # 如果没有检测到函数定义，直接返回原来的插桩脚本
        if not func_defs:
            # 构建插桩脚本
            instrumented = []
            instrumented.append('#!/usr/bin/env bash')
            instrumented.append(self._make_fastboot_wrapper())
            instrumented.append('')
            instrumented.append(f'# === 原始脚本: {os.path.basename(script_path)} ===')
            instrumented.append(f'cd "{work_dir}"')
            instrumented.append('')
            instrumented.extend(lines)
            instrumented.append('__hydra_cleanup')
            return '\n'.join(instrumented)

        # 分离函数定义和非函数代码
        # 从后往前取函数块，避免行号偏移
        func_lines_set = set()
        for start, end in func_defs:
            for ln in range(start, end):
                func_lines_set.add(ln)

        non_func_lines = []
        func_blocks = []
        for ln in range(len(lines)):
            if ln in func_lines_set:
                continue
            non_func_lines.append(lines[ln])

        # 收集函数定义文本
        for start, end in func_defs:
            block = '\n'.join(lines[start:end])
            func_blocks.append(block)

        # 构建插桩脚本：包装器 → 函数定义 → 非函数代码
        instrumented = []
        instrumented.append('#!/usr/bin/env bash')
        instrumented.append(self._make_fastboot_wrapper())
        instrumented.append('')
        instrumented.append(f'# === 原始脚本: {os.path.basename(script_path)} ===')
        instrumented.append(f'cd "{work_dir}"')
        instrumented.append('')

        # 函数定义提前
        instrumented.append('# ---------- 函数定义（已提前） ----------')
        instrumented.extend(func_blocks)
        # 在函数定义后、主逻辑前，确保包装器路径不被覆盖
        instrumented.append('')
        instrumented.append('# 重新确保包装器路径（防止函数定义或初始化覆盖）')
        instrumented.append('export FASTBOOT="$__hydra_wrapper_dir/fastboot"')
        instrumented.append('export ADB="$__hydra_wrapper_dir/adb"')
        instrumented.append('export PATH="$__hydra_wrapper_dir:$PATH"')
        instrumented.append('')
        instrumented.append('# ---------- 脚本主逻辑 ----------')

        # 非函数代码（自动注释掉控制变量覆盖）
        control_vars = {'FASTBOOT', 'ADB', 'AUTO_FLASH', 'WIPE_DATA', 'SKIP_CHECK', 'NO_REBOOT', 'IMG_DIR', 'FASTBOOT_DEFAULT', 'IMG_DIR_DEFAULT'}
        for line in non_func_lines:
            # 注释掉所有对控制变量的重新赋值（防止覆盖包装器预设）
            m = re.match(r'^\s*(\w+)\s*=', line)
            if m and m.group(1) in control_vars:
                instrumented.append('# ' + line + '  # 已被 Hydra 插桩接管')
            else:
                instrumented.append(line)

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