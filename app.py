#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# flash_tool/app.py
"""
Termux 网页刷机 - 应用入口
用无 Root 手机给另一台手机刷机

================== 启动方式 ==================

    python app.py              # 仅本机访问
    python app.py --lan        # 局域网访问（手机IP:8080）
    python app.py --port 9090  # 自定义端口

启动后浏览器访问: http://127.0.0.1:8080
"""

import os
import sys

from flask import Flask, send_from_directory, request, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS

from config import (
    TOOL_VERSION,
    UPDATE_CHECK_URL,
    SECRET_KEY,
    STATIC_DIR,
    ROM_DIR,
    FASTBOOT_PATH,
    ADB_PATH,
    init_directories,
)

from core.utils import diagnose_error
from core.flasher import _load_flash_history
from core import updater

from routes.socketio import init_socketio, register_socketio_events
from routes.api_rom import rom_bp
from routes.api_public import public_bp
from routes.api_images import images_bp
from routes.api_flash import flash_bp
from routes.api_device import device_bp
from routes.api_toolbox import toolbox_bp
from routes.api_usb import usb_bp
from routes.api_batch import batch_task_bp


# ============ Flask 应用 ============
app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY

# 创建 SocketIO 实例
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25
)

# 允许跨域访问（GitHub Pages 部署时需要）
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 注入 socketio 引用到 routes.socketio，并注册所有事件
init_socketio(socketio)
register_socketio_events(socketio)

# 注册所有 Blueprint
app.register_blueprint(rom_bp)
app.register_blueprint(public_bp)
app.register_blueprint(images_bp)
app.register_blueprint(flash_bp)
app.register_blueprint(device_bp)
app.register_blueprint(toolbox_bp)
app.register_blueprint(usb_bp)
app.register_blueprint(batch_task_bp)


# ============ 错误诊断 API ============
@app.route('/api/diagnose', methods=['POST'])
def diagnose_route():
    """接受错误消息文本，返回诊断结果"""
    data = request.get_json(silent=True) or {}
    error_msg = data.get("error", "")
    diagnosis = diagnose_error(error_msg)
    result = {
        "success": True,
        "diagnosis": diagnosis,
    }
    return jsonify(result)


# ============ 版本/更新路由 ============
@app.route('/api/version')
def api_version():
    """获取当前版本信息"""
    return jsonify({
        "success": True,
        "version": TOOL_VERSION,
        "update_url": UPDATE_CHECK_URL
    })


@app.route('/api/update/check')
def api_update_check():
    """检查更新（委托给 core.updater）"""
    return jsonify(updater.check_update())


@app.route('/api/update/do', methods=['POST'])
def api_update_do():
    """执行更新（委托给 core.updater）"""
    return jsonify(updater.do_update())


@app.route('/api/history', methods=['GET'])
def flash_history_route():
    return jsonify({"success": True, "history": _load_flash_history()})


@app.route('/api/shell/run_single', methods=['POST'])
def api_shell_run_single():
    """工作台：执行单条 shell 命令"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        command = str(data.get('command', '')).strip()
        timeout = int(data.get('timeout', 120))
        if not command:
            return jsonify({"success": False, "error": "命令为空"})
        # 安全检查：禁止破坏性命令（rm -rf / 等），使用正则匹配以覆盖多空格变体
        import re
        DANGEROUS_PATTERNS = [
            r'rm\s+(-[rf]+\s+)+/',      # rm -rf / 等
            r'rm\s+(-[rf]+\s+)+~',      # rm -rf ~
            r'mkfs\.',                    # mkfs 格式化
            r'dd\s+.*of=/dev/',          # dd 写入设备
            r'shutdown',                  # shutdown 关机
            r'>\s*/dev/sd',              # 写入磁盘设备
            r'flash_\s*all',             # flash_all
            r':\(\)\s*\{\s*:\|:\s*&\s*\}\s*;',  # fork bomb（保持原有语义）
        ]
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return jsonify({"success": False, "error": f"危险命令已被拦截: {pattern}"})
        import subprocess
        env = os.environ.copy()
        env['PATH'] = (os.path.dirname(str(FASTBOOT_PATH)) + ':' + env.get('PATH', '')) if FASTBOOT_PATH else env.get('PATH', '')
        env['FASTBOOT'] = FASTBOOT_PATH or ''
        env['ADB'] = ADB_PATH or ''
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=ROM_DIR, env=env
        )
        combined = (result.stdout or '') + (result.stderr or '')
        return jsonify({
            "success": result.returncode == 0,
            "output": result.stdout or '',
            "error": result.stderr or '',
            "combined": combined.strip(),
            "returncode": result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": f"命令执行超时（{timeout}秒）"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# 主页路由 - 返回前端页面
@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')


def run_server(host='127.0.0.1', port=8080, debug=False):
    """启动服务器"""
    # 启动前确保必要目录就绪
    init_directories()

    print("=" * 50)
    print("  Termux 网页刷机 (All-In-One)")
    print("=" * 50)
    print(f"  本机访问: http://127.0.0.1:{port}")
    if host == '0.0.0.0':
        print(f"  局域网访问: http://<手机IP>:{port}")
    print("=" * 50)

    socketio.run(
        app,
        host=host,
        port=port,
        debug=debug,
        allow_unsafe_werkzeug=True
    )


def print_help():
    print("""用法: python app.py [选项]

选项:
  --host HOST    监听主机 (默认: 127.0.0.1)
  --port PORT    监听端口 (默认: 8080)
  --lan          监听所有网卡 (允许局域网访问)
  -h, --help     显示此帮助信息

示例:
  python app.py                # 仅本机访问
  python app.py --lan          # 局域网访问
  python app.py --port 9090    # 自定义端口
""")


if __name__ == '__main__':
    host = '127.0.0.1'
    port = 8080

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ('-h', '--help'):
            print_help()
            sys.exit(0)
        elif arg == '--host' and i + 1 < len(args):
            host = args[i + 1]
            i += 2
            continue
        elif arg == '--port' and i + 1 < len(args):
            try:
                port = int(args[i + 1])
            except ValueError:
                print(f"错误: 无效端口 {args[i + 1]}")
                sys.exit(1)
            i += 2
            continue
        elif arg == '--lan':
            host = '0.0.0.0'
        else:
            print(f"未知参数: {arg}")
            print_help()
            sys.exit(1)
        i += 1

    try:
        run_server(host=host, port=port)
    except KeyboardInterrupt:
        print("\n服务器已停止")
        sys.exit(0)