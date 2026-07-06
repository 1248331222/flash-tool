#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Skytree Flasher / routes/socketio.py
"""SocketIO 事件处理与任务推送模块

socketio 对象在 app.py 中创建，本模块通过 init_socketio() 接收引用。
事件处理函数以普通函数形式定义，由 register_socketio_events() 统一注册。
"""

from config import logger
from core.extractor import get_task_status

# socketio 对象引用，由 app.py 通过 init_socketio() 注入
socketio = None


def init_socketio(sio):
    """由 app.py 调用，注入 SocketIO 实例引用"""
    global socketio
    socketio = sio


# ============ WebSocket 事件处理函数 ============

def handle_connect():
    logger.info('WebSocket 客户端已连接')
    socketio.emit('connected', {'msg': 'WebSocket 连接成功'})


def handle_disconnect():
    logger.info('WebSocket 客户端已断开')


def handle_task_update_request(data):
    task_id = data.get('task_id')
    if task_id:
        result = get_task_status(task_id)
        socketio.emit('task_update', result)


def register_socketio_events(sio):
    """注册所有 SocketIO 事件"""
    sio.on_event('connect', handle_connect)
    sio.on_event('disconnect', handle_disconnect)
    sio.on_event('request_task_update', handle_task_update_request)


# ============ 任务进度推送函数 ============

def emit_task_progress(task_id, progress, message):
    """推送任务进度"""
    if socketio is None:
        return
    socketio.emit('task_progress', {
        'task_id': task_id,
        'progress': progress,
        'message': message
    })


def emit_task_complete(task_id, success, message):
    """推送任务完成"""
    if socketio is None:
        return
    socketio.emit('task_complete', {
        'task_id': task_id,
        'success': success,
        'message': message
    })


def emit_error_diagnosis(error, diagnosis):
    """推送错误诊断"""
    if socketio is None:
        return
    socketio.emit('error_diagnosis', {
        'error': error,
        'diagnosis': diagnosis
    })