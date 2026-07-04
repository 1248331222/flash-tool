# Skytree Flasher / routes/api_batch_helpers.py
# -*- coding: utf-8 -*-
"""
routes/api_batch_helpers.py — 批量刷机路由辅助函数
从 routes/api_batch.py 拆分而来，函数逻辑保持不变。

包含任务公开化、fastboot 路径重写、重连等待注入、Shell 模拟执行。
socketio 通过延迟导入（函数内）获取 routes.socketio 注入的最新引用。
"""

import re
import time


def public_task(task: dict) -> dict:
    if not task:
        return {}
    result = {
        "id": task.get("id"),
        "type": task.get("type"),
        "status": task.get("status"),
        "phase": task.get("phase"),
        "progress": task.get("progress", 0),
        "error": task.get("error", ""),
        "diagnosis": task.get("diagnosis", ""),
        "category": task.get("category", ""),
        "source": task.get("source", ""),
        "rom_name": task.get("rom_name", ""),
        "step_total": task.get("step_total", 0),
        "steps": task.get("steps") or [],
        "current_index": task.get("current_index", 0),
        "next_index": task.get("next_index", 0),
        "current_step": task.get("current_step", {}),
        "logs": (task.get("logs") or [])[-120:],
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
    }
    # direct_execute 类型的额外字段
    if task.get("type") == "direct_execute":
        result["output"] = (task.get("output") or [])[-200:]
        result["errors"] = task.get("errors") or []
        result["dry_run"] = task.get("dry_run", False)
        result["total_lines"] = task.get("total_lines", 0)
        result["current_line"] = task.get("current_line", 0)
    return result


def force_rewrite_fastboot_paths(sh_content):
    """
    v3.0.4: 在临时脚本副本上预处理，将各种已知的 fastboot/adb 路径统一替换为 $FASTBOOT/$ADB 变量引用。
    不修改用户原始脚本，只改临时 _converted_flash.sh。
    覆盖场景：硬编码系统路径、用户自定义变量中的路径、相对路径、BAT 残留 %变量% 等。
    
    注意：跳过赋值语句（VAR=...），避免 TOOL_PATH="$CURRENT_DIR/tools/fastboot" 中的
    tools/fastboot 被误替换，导致路径拼接错误。赋值语句中的路径由后续
    inject_reconnect_wait 注入的变量覆盖来处理。
    """
    # 需要替换的已知路径模式（按长度降序排列，避免短路径先匹配导致长路径替换不完整）
    # 每项为 (模式, 替换目标变量名)
    path_patterns = [
        ('/data/data/com.termux/files/usr/bin/fastboot', 'FASTBOOT'),
        ('/data/data/com.termux/files/home/.termux-adb/fastboot', 'FASTBOOT'),
        ('/data/data/com.termux/files/usr/bin/adb', 'ADB'),
        ('/data/data/com.termux/files/home/.termux-adb/adb', 'ADB'),
        ('/system/bin/fastboot', 'FASTBOOT'),
        ('/system/xbin/fastboot', 'FASTBOOT'),
        ('/system/bin/adb', 'ADB'),
        ('/system/xbin/adb', 'ADB'),
        # 相对路径
        ('tools/termux-fastboot', 'FASTBOOT'),
        ('tools/fastboot.exe', 'FASTBOOT'),
        ('tools/adb.exe', 'ADB'),
        ('tools/fastboot', 'FASTBOOT'),
        ('tools/adb', 'ADB'),
        # BAT 残留 %变量% 形式
        ('%TOOL_PATH%', 'FASTBOOT'),
        ('%CURRENT_DIR%tools\\fastboot.exe', 'FASTBOOT'),
        ('%CURRENT_DIR%tools/termux-fastboot', 'FASTBOOT'),
    ]

    # 赋值模式：检测行是否为 VAR=... 或 export/readonly/local VAR=... 赋值
    assign_re = re.compile(r'^(?:export\s+|readonly\s+|local\s+)?[a-zA-Z_]\w*\s*=')

    result_lines = []
    for line in sh_content.splitlines():
        stripped = line.strip()

        # 跳过注释行（不替换注释中的路径）
        if stripped.startswith('#'):
            result_lines.append(line)
            continue

        # 赋值语句：跳过路径替换，保持原样
        # 因为赋值中的路径被替换为 $FASTBOOT 会导致路径拼接错误
        # （如 TOOL_PATH="$CURRENT_DIR/tools/fastboot" → TOOL_PATH="$CURRENT_DIR/$FASTBOOT"）
        if assign_re.match(stripped):
            result_lines.append(line)
            continue

        modified = line
        for pat, var_name in path_patterns:
            target_var = f'${var_name}'

            # 替换带引号的路径："xxx/fastboot" → "$FASTBOOT"
            modified = modified.replace(f'"{pat}"', f'"{target_var}"')
            modified = modified.replace(f"'{pat}'", f"'{target_var}'")

            # 替换无引号的路径
            modified = re.sub(
                r'(?<![a-zA-Z0-9_./\-])' + re.escape(pat) + r'(?![a-zA-Z0-9_.])',
                target_var,
                modified
            )

        result_lines.append(modified)

    return '\n'.join(result_lines)


def inject_reconnect_wait(sh_content):
    """
    v3.0.3: 在脚本中注入设备重连等待函数和 fastboot 命令覆盖函数。
    扫描脚本中的 fastboot/adb reboot bootloader/fastboot 命令，
    在脚本开头注入 __trae_wait_reconnect 和 fastboot() 函数定义，
    在每个 reboot 命令后插入等待调用。
    fastboot() 函数优先级高于外部命令，确保脚本中的 fastboot 调用
    始终使用项目内置/免root 版本的二进制。
    返回注入后的脚本内容。
    """
    # 变量覆盖放在脚本末尾，确保最后生效，避免被原始赋值覆盖
    var_overrides = '''# === Hydra 注入：fastboot 路径变量覆盖（放在末尾确保最后生效） ===
# 将常见的 fastboot 路径变量强制指向项目内置的 fastboot
# 这样脚本中的 "$TOOL_PATH" 等变量直接使用正确的 fastboot
TOOL_PATH="$FASTBOOT"
FASTBOOT_PATH="$FASTBOOT"
FB_PATH="$FASTBOOT"

'''

    wait_func = '''__trae_wait_reconnect() {
    local target_mode="$1"
    local max_wait=180
    local waited=0
    echo "[TRAE_WAIT] 设备已发送 reboot $target_mode，先等待 2 秒让设备离线..."
    sleep 2
    echo "[TRAE_WAIT] 开始检测设备重连..."
    while [ $waited -lt $max_wait ]; do
        local dev_count=$($FASTBOOT devices 2>/dev/null | wc -l)
        if [ "$dev_count" -gt 0 ]; then
            echo "[TRAE_WAIT] 设备已重新连接 (${waited}秒)"
            return 0
        fi
        # 每 10 秒检查 USB 设备是否存在但无授权，尝试自动重新授权
        if [ $((waited % 10)) -eq 0 ] && [ $waited -ge 5 ]; then
            local usb_devices
            usb_devices=$(termux-usb -l 2>/dev/null)
            if [ -n "$usb_devices" ] && [ "$usb_devices" != "" ]; then
                echo "[TRAE_WAIT] 检测到 USB 设备但 Fastboot 不可用，正在自动重新授权..."
                local first_device
                first_device=$(echo "$usb_devices" | head -1)
                termux-usb -r "$first_device" 2>/dev/null
            fi
        fi
        sleep 1
        waited=$((waited + 1))
        if [ $((waited % 15)) -eq 0 ] && [ $waited -ge 10 ]; then
            echo "[TRAE_WAIT] 已等待 ${waited} 秒，检测到设备后自动继续..."
        fi
    done
    echo "[TRAE_WAIT] 等待设备重连超时 (${max_wait}秒)"
    return 1
}

# fastboot 命令覆盖：Bash 函数优先级高于外部命令
# 确保脚本中的裸 fastboot 调用始终使用正确版本
fastboot() {
    if [ -n "${FASTBOOT:-}" ] && [ -x "$FASTBOOT" ]; then
        "$FASTBOOT" "$@"
    elif command -v fastboot >/dev/null 2>&1; then
        command fastboot "$@"
    else
        echo "[ERROR] 未找到可用的 fastboot 二进制文件" >&2
        return 1
    fi
}

'''

    lines = sh_content.splitlines()
    new_lines = []
    # 匹配 reboot 命令行，保留原始缩进
    # 匹配多种形式：
    #   fastboot reboot bootloader
    #   "$TOOL_PATH" reboot fastboot
    #   $FASTBOOT reboot bootloader
    # 使用非 VERBOSE 模式，精确匹配空格
    reboot_re = re.compile(
        r'^(\s*)'
        r'(?:'
        r'fastboot|adb'                              # 裸命令
        r'|\$\{?\w+\}?'                               # $VAR 或 ${VAR}
        r'|"[^"]*"'                                    # "$VAR" 或任何引号内容
        r')'
        r'(\s+reboot\s+(bootloader|fastboot))'
        r'(\s*.*)$',
        re.IGNORECASE
    )

    # 需要被替换为 $FASTBOOT 的 fastboot 路径变量名
    fb_var_names = ['TOOL_PATH', 'FASTBOOT_PATH', 'FB_PATH', 'FB', 'FLASHTOOL']

    for line in lines:
        # 替换 fastboot 路径变量赋值（如 TOOL_PATH="...fastboot" → TOOL_PATH="$FASTBOOT"）
        # 确保脚本中的 $TOOL_PATH 在文件存在检查前就指向正确的 fastboot
        modified_line = line
        for vname in fb_var_names:
            # 匹配 VAR="path" 或 VAR='path' 或 VAR=path
            vre = re.compile(
                r'^(\s*)' + re.escape(vname) + r'\s*=\s*(["\']?).*?(?:fastboot|adb).*?\2\s*$',
                re.IGNORECASE
            )
            if vre.match(modified_line):
                modified_line = f'{vname}="$FASTBOOT"'
                break
        new_lines.append(modified_line)
        m = reboot_re.match(modified_line)
        if m:
            indent = m.group(1)
            target = m.group(4).lower()
            new_lines.append(f'{indent}__trae_wait_reconnect {target}')

    result = wait_func + '\n'.join(new_lines) + var_overrides
    return result


def _simulate_sh_execution(task, sh_content):
    """
    v3.0.1: 模拟执行 Shell 脚本（dry_run 模式）
    在 reboot 行提示设备将断开，并模拟等待重连
    """
    # socketio 由 app.py 注入到 routes.socketio，此处延迟导入获取最新引用
    from routes.socketio import socketio
    import random
    lines = sh_content.split('\n')
    total = len(lines)
    fb_outputs = {
        'flash': 'Sending \'{0}\' ... OK\nWriting \'{0}\' ... OK',
        'erase': 'Erasing \'{}\' ... OK',
        'boot': 'Booting ... OK',
        'reboot': 'Rebooting...',
        'oem': 'OK',
        'flashing': 'OK',
        'delete-logical-partition': 'Deleted logical partition {}',
        'resize-partition': 'Resized partition {}',
        'set_active': 'Setting current slot to {}',
    }
    # flash 命令前可能出现的 fastboot 选项标志
    fb_flags = {'--disable-verity', '--disable-verification', '--skip-reboot',
                '--force', '--slot', '--no-verify', '--disable-verity --disable-verification'}
    reboot_re = re.compile(r'^\s*(fastboot|adb)\s+reboot\s+(bootloader|fastboot)', re.IGNORECASE)
    wait_re = re.compile(r'^\s*__trae_wait_reconnect\s+(bootloader|fastboot)')

    # 状态机：跟踪是否在注入的函数定义内部
    in_injected_func = False  # 当前行是否在 __trae_wait_reconnect 或 fastboot() 函数体内

    for idx, line in enumerate(lines):
        stripped = line.strip()
        task["current_line"] = idx + 1

        # --- 状态机：检测注入函数进入/离开 ---
        if stripped.startswith('__trae_wait_reconnect()') or stripped.startswith('fastboot()'):
            in_injected_func = True
            continue
        if stripped == '}' and in_injected_func:
            in_injected_func = False
            continue
        if in_injected_func:
            # 函数体内的所有行全部跳过（包括 while/if/return/echo/local 等）
            continue

        if (not stripped or stripped.startswith('#') or stripped.startswith('!')
            or stripped.startswith('#!/') or stripped.startswith('set ')
            or stripped in ('then', 'fi', 'do', 'done', 'else', ':')
            or stripped.startswith('echo -ne')):
            continue

        # 模拟等待函数调用
        wm = wait_re.match(stripped)
        if wm:
            target = wm.group(1).lower()
            task["output"].append(f'[模拟] [TRAE_WAIT] 设备重启中，等待重连...')
            time.sleep(0.5)
            task["output"].append(f'[模拟] [TRAE_WAIT] 设备已重新连接，自动继续执行')
            try:
                socketio.emit('task_progress', {
                    "task_id": task["task_id"],
                    "type": "direct_execute",
                    "message": f"[TRAE_WAIT] 等待设备重连 ({target})...",
                    "progress": int((idx + 1) / max(total, 1) * 100),
                    "line": stripped,
                    "current_line": idx + 1,
                    "total_lines": total,
                    "dry_run": True,
                })
            except:
                pass
            continue

        rm = reboot_re.search(stripped)
        if rm:
            target = rm.group(2).lower()
            task["output"].append(f'[模拟] [REBOOT] {stripped}')
            try:
                socketio.emit('task_progress', {
                    "task_id": task["task_id"],
                    "type": "direct_execute",
                    "message": f"[REBOOT] 设备将重启到 {target}...",
                    "progress": int((idx + 1) / max(total, 1) * 100),
                    "line": stripped,
                    "current_line": idx + 1,
                    "total_lines": total,
                    "dry_run": True,
                })
            except:
                pass
            continue

        is_fb = '$FASTBOOT' in stripped or 'fastboot' in stripped.lower()
        time.sleep(0.05 if not is_fb else random.uniform(0.15, 0.4))

        if is_fb:
            parts = stripped.replace('$FASTBOOT', 'fastboot').split()
            if len(parts) >= 2:
                # 跳过 fastboot 选项标志（如 --disable-verity），找到实际命令
                cmd_idx = 1
                while cmd_idx < len(parts) and parts[cmd_idx].startswith('-'):
                    cmd_idx += 1
                if cmd_idx >= len(parts):
                    cmd_idx = 1  # fallback
                cmd = parts[cmd_idx]
                raw_args = ' '.join(parts[cmd_idx + 1:]) if len(parts) > cmd_idx + 1 else ''
                # 去掉重定向符号及其后面的内容（如 >/dev/null 2>&1）
                args = raw_args.split('>')[0].strip().strip('"').strip("'")
                # flash 命令：只取分区名作为参数（忽略文件路径）
                if cmd == 'flash' and args:
                    arg_parts = args.split()
                    if arg_parts:
                        args = arg_parts[0].strip('"').strip("'")
                if cmd in fb_outputs:
                    out = fb_outputs[cmd].format(args)
                    task["output"].append(f'[模拟] {stripped}')
                    task["output"].append(f'[模拟]   -> {out.strip()}')
                else:
                    task["output"].append(f'[模拟] {stripped}')
                    task["output"].append(f'[模拟]   -> OK')
            else:
                task["output"].append(f'[模拟] {stripped}')
        elif stripped.startswith('echo ') or stripped == 'echo':
            msg = stripped[5:].strip().strip('"').strip("'")
            if msg:
                task["output"].append(f'[模拟] {msg}')
        elif stripped.startswith('read ') or stripped.startswith('sleep '):
            task["output"].append(f'[模拟] {stripped} (跳过等待)')
        elif stripped.startswith('cd ') or stripped.startswith('clear'):
            task["output"].append(f'[模拟] {stripped}')
        elif stripped.startswith('for ') or stripped.startswith('if '):
            task["output"].append(f'[模拟] {stripped}')
        else:
            task["output"].append(f'[模拟] {stripped}')

        try:
            socketio.emit('task_progress', {
                "task_id": task["task_id"],
                "type": "direct_execute",
                "message": stripped,
                "progress": int((idx + 1) / max(total, 1) * 100),
                "line": stripped,
                "current_line": idx + 1,
                "total_lines": total,
                "dry_run": True,
            })
        except:
            pass

    task["status"] = "completed"
    task["phase"] = "completed"
    task["output"].append('[模拟] ========== 模拟执行完成 ==========')