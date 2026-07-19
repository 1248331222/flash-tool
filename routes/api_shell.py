# Skytree Flasher / routes/api_shell.py
"""Shell 命令执行 API — 供设备页面自定义命令功能使用

仅后端模式可用（Termux 环境），WebUSB 模式由前端拦截并提示不可用。

特性：
- 会话工作目录持久化：cd 命令会真正改变后续命令的工作目录
- 完整 Termux 环境变量：支持 termux-usb/pkg/am 等专有命令
- 登录 shell（bash -l -c）：加载 .profile/.bashrc
"""

import os
import re
import shlex
import subprocess
from flask import Blueprint, request, jsonify

from config import logger, FASTBOOT_PATH, ADB_PATH

shell_bp = Blueprint('shell', __name__, url_prefix='/api/shell')

# 最大超时时间（秒），刷写大镜像（如 super.img）可能需要很长时间
SHELL_MAX_TIMEOUT = 1800  # 30 分钟
# 默认超时（秒）
SHELL_DEFAULT_TIMEOUT = 300  # 5 分钟

# Termux 标准路径
TERMUX_PREFIX = '/data/data/com.termux/files/usr'
TERMUX_BIN = TERMUX_PREFIX + '/bin'
TERMUX_LIB = TERMUX_PREFIX + '/lib'
TERMUX_TMP = TERMUX_PREFIX + '/tmp'

# 默认工作目录（Termux home 或当前进程工作目录）
DEFAULT_CWD = os.environ.get('HOME', os.getcwd())

# ============ 会话工作目录管理 ============
# 按 session_id 保存每个会话的当前工作目录
# 前端通过 localStorage 生成并保存 session_id，保证同一浏览器标签页的会话一致
_session_cwd = {}
# 会话最后活跃时间（用于清理过期会话）
_session_last_active = {}

# 会话过期时间（秒）：2 小时未活跃的会话自动清理
SESSION_EXPIRE_SECONDS = 7200

# 最多保存的会话数（防止内存泄漏）
MAX_SESSIONS = 50


def _cleanup_expired_sessions():
    """清理过期的会话工作目录"""
    import time
    now = time.time()
    expired = [sid for sid, t in _session_last_active.items() if now - t > SESSION_EXPIRE_SECONDS]
    for sid in expired:
        _session_cwd.pop(sid, None)
        _session_last_active.pop(sid, None)
    # 如果会话数仍然过多，清理最旧的
    if len(_session_cwd) > MAX_SESSIONS:
        sorted_sids = sorted(_session_last_active.items(), key=lambda x: x[1])
        for sid, _ in sorted_sids[:len(_session_cwd) - MAX_SESSIONS]:
            _session_cwd.pop(sid, None)
            _session_last_active.pop(sid, None)


def _get_session_cwd(session_id):
    """获取会话当前工作目录"""
    if session_id and session_id in _session_cwd:
        return _session_cwd[session_id]
    return DEFAULT_CWD


def _set_session_cwd(session_id, cwd):
    """设置会话当前工作目录"""
    if session_id:
        _session_cwd[session_id] = cwd
        import time
        _session_last_active[session_id] = time.time()


def _touch_session(session_id):
    """更新会话活跃时间"""
    if session_id:
        import time
        _session_last_active[session_id] = time.time()


def _is_pure_cd_command(command):
    """检测是否是纯 cd 命令（不包含 && ; | || & 等命令分隔符）

    纯 cd 命令需要特殊处理：更新会话工作目录
    复合命令（如 cd /tmp && ls）则正常执行，不更新会话目录
    """
    cmd = command.strip()
    if not cmd.startswith('cd'):
        return False
    # cd 后面必须是空格、制表符或结束
    if len(cmd) > 2 and cmd[2] not in (' ', '\t'):
        return False
    # 不能包含命令分隔符（支持多行脚本，所以 \n 也算分隔符）
    for sep in ['&&', '||', ';', '|', '&', '\n']:
        if sep in cmd:
            return False
    return True


def _resolve_cd_target(command, current_cwd, env):
    """解析 cd 命令的目标目录

    支持:
        cd /absolute/path
        cd ~/path
        cd ../path
        cd relative/path
        cd ~ (回家目录)
        cd (回家目录)

    返回:
        (success, new_cwd, error_message)
    """
    cmd = command.strip()
    # 提取 cd 后面的参数
    parts = cmd.split(None, 1)
    target = parts[1].strip() if len(parts) > 1 else ''

    # 去除引号
    if target:
        if (target[0] == '"' and target[-1] == '"') or (target[0] == "'" and target[-1] == "'"):
            target = target[1:-1]
        # 去除尾部斜杠
        target = target.rstrip('/') if len(target) > 1 else target

    # 解析目标目录
    if not target or target == '~':
        new_cwd = env.get('HOME', os.path.expanduser('~'))
    elif target.startswith('~/'):
        new_cwd = os.path.expanduser(target)
    elif target.startswith('~'):
        # ~username 形式（termux 下很少用）
        new_cwd = os.path.expanduser(target)
    elif os.path.isabs(target):
        new_cwd = target
    else:
        new_cwd = os.path.normpath(os.path.join(current_cwd, target))

    # 检查目录是否存在
    if not os.path.exists(new_cwd):
        return False, current_cwd, f"bash: cd: {target}: No such file or directory"
    if not os.path.isdir(new_cwd):
        return False, current_cwd, f"bash: cd: {target}: Not a directory"

    return True, new_cwd, ""


def _build_termux_env():
    """构建完整的 Termux 环境变量，确保 termux 命令（termux-usb/pkg/am 等）可用。

    后端运行在 Termux 上，Python 进程继承的环境可能不完整
   （特别是通过非交互方式启动时），因此显式补全关键变量。
    """
    env = os.environ.copy()

    # 如果检测到 Termux 环境，补全关键路径
    is_termux = os.path.isdir(TERMUX_PREFIX)
    if is_termux:
        # 确保 Termux bin 目录在 PATH 最前面
        current_path = env.get('PATH', '')
        path_parts = current_path.split(':') if current_path else []
        # 把 termux bin 放到最前面（如果不在的话）
        if TERMUX_BIN not in path_parts:
            env['PATH'] = TERMUX_BIN + ':' + current_path
        elif path_parts[0] != TERMUX_BIN:
            # 已存在但不在最前面，移到最前面
            path_parts = [p for p in path_parts if p != TERMUX_BIN]
            env['PATH'] = TERMUX_BIN + ':' + ':'.join(path_parts)

        # 补全 Termux 专有环境变量
        env.setdefault('PREFIX', TERMUX_PREFIX)
        env.setdefault('TMPDIR', TERMUX_TMP)
        env.setdefault('LD_LIBRARY_PATH', TERMUX_LIB)

    # 把 fastboot / adb 所在目录加到 PATH（与 /api/shell/run_single 保持一致）
    for tool_path in (FASTBOOT_PATH, ADB_PATH):
        if tool_path:
            tool_dir = os.path.dirname(str(tool_path))
            current_path = env.get('PATH', '')
            if tool_dir and tool_dir not in current_path.split(':'):
                env['PATH'] = tool_dir + ':' + current_path

    # 注入工具路径供脚本使用
    env['FASTBOOT'] = str(FASTBOOT_PATH) if FASTBOOT_PATH else ''
    env['ADB'] = str(ADB_PATH) if ADB_PATH else ''

    return env


@shell_bp.route('/run', methods=['POST'])
def shell_run():
    """执行 shell 命令或脚本

    请求体:
        {
            "command": "ls -la",       # 单条命令或多行脚本
            "timeout": 30,              # 可选，超时秒数
            "mode": "bash",             # 可选，bash|sh，默认 bash
            "session_id": "xxx"         # 可选，会话ID（用于保持工作目录）
        }

    返回:
        {
            "success": true/false,
            "returncode": 0,
            "stdout": "...",
            "stderr": "...",
            "combined": "...",
            "cwd": "/current/working/dir"  # 当前工作目录
        }
    """
    data = request.get_json(silent=True) or {}
    command = (data.get('command') or '').strip()
    timeout = min(int(data.get('timeout', SHELL_DEFAULT_TIMEOUT)), SHELL_MAX_TIMEOUT)
    mode = data.get('mode', 'bash')
    session_id = data.get('session_id', 'default')

    if not command:
        return jsonify({"success": False, "error": "命令不能为空"}), 400

    if mode not in ('bash', 'sh'):
        mode = 'bash'

    # 清理过期会话
    _cleanup_expired_sessions()

    # 获取会话当前工作目录
    current_cwd = _get_session_cwd(session_id)
    _touch_session(session_id)

    # 构建完整的 Termux 环境变量
    env = _build_termux_env()

    logger.info(f"[shell] 执行命令 (mode={mode}, timeout={timeout}s, cwd={current_cwd}, session={session_id}): {command[:200]}")

    # 特殊处理：纯 cd 命令（更新会话工作目录，不产生输出）
    if _is_pure_cd_command(command):
        ok, new_cwd, err_msg = _resolve_cd_target(command, current_cwd, env)
        if ok:
            _set_session_cwd(session_id, new_cwd)
            logger.info(f"[shell] cd 成功: {current_cwd} -> {new_cwd} (session={session_id})")
            return jsonify({
                "success": True,
                "returncode": 0,
                "stdout": "",
                "stderr": "",
                "combined": "",
                "cwd": new_cwd
            })
        else:
            # cd 失败（目录不存在等），不改变工作目录
            return jsonify({
                "success": False,
                "returncode": 1,
                "stdout": "",
                "stderr": err_msg,
                "combined": err_msg,
                "cwd": current_cwd
            })

    try:
        # 使用 bash -l -c 执行命令（登录 shell，加载 .profile/.bashrc）
        # 先 cd 到会话工作目录，再执行命令
        # 用 shlex.quote 安全地引用目录路径
        wrapped_command = 'cd ' + shlex.quote(current_cwd) + ' && ' + command

        res = subprocess.run(
            [mode, '-l', '-c', wrapped_command],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )

        stdout = res.stdout or ''
        stderr = res.stderr or ''
        combined = stdout + stderr

        return jsonify({
            "success": res.returncode == 0,
            "returncode": res.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "combined": combined,
            "cwd": current_cwd
        })

    except subprocess.TimeoutExpired:
        logger.warning(f"[shell] 命令执行超时 ({timeout}s)")
        return jsonify({
            "success": False,
            "error": f"命令执行超时（{timeout}秒）",
            "returncode": -1,
            "stdout": "",
            "stderr": f"Timeout after {timeout}s",
            "combined": f"命令执行超时（{timeout}秒）",
            "cwd": current_cwd
        }), 200
    except Exception as e:
        logger.error(f"[shell] 命令执行失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "combined": str(e),
            "cwd": current_cwd
        }), 200


@shell_bp.route('/cwd', methods=['GET'])
def shell_get_cwd():
    """获取会话当前工作目录

    查询参数:
        session_id: 会话ID
    """
    session_id = request.args.get('session_id', 'default')
    cwd = _get_session_cwd(session_id)
    return jsonify({
        "success": True,
        "cwd": cwd,
        "default_cwd": DEFAULT_CWD
    })


@shell_bp.route('/reset', methods=['POST'])
def shell_reset_cwd():
    """重置会话工作目录到默认目录

    请求体:
        {
            "session_id": "xxx"
        }
    """
    data = request.get_json(silent=True) or {}
    session_id = data.get('session_id', 'default')
    _session_cwd.pop(session_id, None)
    _session_last_active.pop(session_id, None)
    return jsonify({
        "success": True,
        "cwd": DEFAULT_CWD,
        "message": "工作目录已重置"
    })
