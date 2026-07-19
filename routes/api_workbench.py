# Skytree Flasher / routes/api_workbench.py
"""工作台配置管理 API — 管理用户保存的工作台配置（步骤列表）"""

import os
import json
import time
from flask import Blueprint, request, jsonify

from config import logger

workbench_bp = Blueprint('workbench', __name__, url_prefix='/api/workbench')

# 配置文件存储目录（项目根目录下的 configs/workbench/）
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'configs', 'workbench')


def _ensure_config_dir():
    """确保配置目录存在"""
    os.makedirs(CONFIG_DIR, exist_ok=True)


def _config_path(name):
    """获取配置文件的完整路径"""
    # 安全检查：禁止路径穿越
    safe_name = os.path.basename(name)
    if not safe_name or safe_name != name:
        return None
    if not safe_name.endswith('.json'):
        safe_name += '.json'
    return os.path.join(CONFIG_DIR, safe_name)


@workbench_bp.route('/configs', methods=['GET'])
def list_configs():
    """列出所有工作台配置"""
    try:
        _ensure_config_dir()
        configs = []
        for entry in os.scandir(CONFIG_DIR):
            if entry.is_file() and entry.name.endswith('.json'):
                name = entry.name[:-5]  # 去掉 .json 后缀
                try:
                    with open(entry.path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    configs.append({
                        'name': name,
                        'step_count': len(data.get('steps', [])),
                        'updated_at': data.get('updated_at', 0),
                        'description': data.get('description', ''),
                    })
                except (json.JSONDecodeError, IOError):
                    configs.append({'name': name, 'step_count': 0, 'updated_at': 0, 'description': ''})
        # 按更新时间倒序
        configs.sort(key=lambda c: c.get('updated_at', 0), reverse=True)
        return jsonify({'success': True, 'configs': configs})
    except Exception as e:
        logger.error(f"列出工作台配置失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workbench_bp.route('/configs/<path:name>', methods=['GET'])
def get_config(name):
    """读取单个工作台配置"""
    try:
        path = _config_path(name)
        if not path or not os.path.isfile(path):
            return jsonify({'success': False, 'error': '配置不存在'}), 404
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({'success': True, 'config': data})
    except Exception as e:
        logger.error(f"读取工作台配置失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workbench_bp.route('/configs', methods=['POST'])
def save_config():
    """保存工作台配置"""
    try:
        data = request.get_json(silent=True) or {}
        name = data.get('name', '').strip()
        steps = data.get('steps', [])
        description = data.get('description', '')

        if not name:
            return jsonify({'success': False, 'error': '配置名称不能为空'}), 400

        _ensure_config_dir()
        path = _config_path(name)
        if not path:
            return jsonify({'success': False, 'error': '配置名称包含非法字符'}), 400

        config_data = {
            'name': name,
            'steps': steps,
            'description': description,
            'updated_at': int(time.time()),
            'version': 1,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        logger.info(f"工作台配置已保存: {name}（{len(steps)} 步）")
        return jsonify({'success': True, 'name': name, 'step_count': len(steps)})
    except Exception as e:
        logger.error(f"保存工作台配置失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workbench_bp.route('/configs/<path:name>', methods=['DELETE'])
def delete_config(name):
    """删除工作台配置"""
    try:
        path = _config_path(name)
        if not path or not os.path.isfile(path):
            return jsonify({'success': False, 'error': '配置不存在'}), 404
        os.remove(path)
        logger.info(f"工作台配置已删除: {name}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"删除工作台配置失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workbench_bp.route('/export', methods=['POST'])
def export_config():
    """导出配置到指定路径"""
    try:
        data = request.get_json(silent=True) or {}
        name = data.get('name', '').strip()
        export_path = data.get('path', '').strip()

        if not name or not export_path:
            return jsonify({'success': False, 'error': '配置名称和导出路径不能为空'}), 400

        # 读取源配置
        src_path = _config_path(name)
        if not src_path or not os.path.isfile(src_path):
            return jsonify({'success': False, 'error': '配置不存在'}), 404

        with open(src_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        # 确保导出路径以 .json 结尾
        if not export_path.endswith('.json'):
            export_path = export_path.rstrip('/') + '/' + name + '.json'

        # 确保目标目录存在
        export_dir = os.path.dirname(export_path)
        if export_dir:
            os.makedirs(export_dir, exist_ok=True)

        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        logger.info(f"工作台配置已导出: {name} → {export_path}")
        return jsonify({'success': True, 'path': export_path})
    except PermissionError:
        return jsonify({'success': False, 'error': '权限不足，无法写入目标路径'}), 403
    except Exception as e:
        logger.error(f"导出工作台配置失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workbench_bp.route('/import', methods=['POST'])
def import_config():
    """从指定路径导入配置"""
    try:
        data = request.get_json(silent=True) or {}
        import_path = data.get('path', '').strip()

        if not import_path:
            return jsonify({'success': False, 'error': '导入路径不能为空'}), 400

        if not os.path.isfile(import_path):
            return jsonify({'success': False, 'error': '文件不存在'}), 404

        with open(import_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        name = config_data.get('name', '')
        steps = config_data.get('steps', [])

        if not name:
            # 从文件名推导名称
            name = os.path.basename(import_path)
            if name.endswith('.json'):
                name = name[:-5]
            config_data['name'] = name

        # 保存到配置目录
        _ensure_config_dir()
        dest_path = _config_path(name)
        if not dest_path:
            return jsonify({'success': False, 'error': '配置名称包含非法字符'}), 400

        config_data['updated_at'] = int(time.time())
        with open(dest_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        logger.info(f"工作台配置已导入: {import_path} → {name}（{len(steps)} 步）")
        return jsonify({'success': True, 'name': name, 'steps': steps, 'step_count': len(steps)})
    except json.JSONDecodeError:
        return jsonify({'success': False, 'error': '文件不是有效的 JSON 配置'}), 400
    except Exception as e:
        logger.error(f"导入工作台配置失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
