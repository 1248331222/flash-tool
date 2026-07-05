// flash_tool/static/js/api.js
// ============ WebSocket 连接 ============
function updateEnvStatusConnection() {
    envStatusEl.className = envStatusBaseClass;
    if (envStatusBaseClass.includes('error')) {
        envStatusEl.style.display = '';
        envStatusEl.textContent = '❌ 后端不可用';
        return;
    }
    envStatusEl.textContent = '';
    envStatusEl.style.display = 'none';
}

function initWebSocket() {
    if (typeof io === 'undefined') {
        writeLog('Socket.IO 库未加载，实时日志将不可用', 'warn');
        return;
    }
    // 使用配置的后端地址连接 WebSocket
    const wsUrl = App.backendUrl || window.location.origin;
    socket = io(wsUrl, {
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: 10,
        reconnectionDelay: 1000
    });
    
    socket.on('connect', () => {
        realtimeConnected = true;
        updateEnvStatusConnection();
        writeLog('WebSocket 连接成功', 'ok');
    });
    
    socket.on('connect_error', (err) => {
        realtimeConnected = false;
        envStatusBaseClass = 'env-status error';
        envStatusBaseText = 'WebSocket 连接失败：' + (err.message || '未知错误');
        updateEnvStatusConnection();
        writeLog('WebSocket 连接失败（将降级为轮询模式）：' + (err.message || '未知错误'), 'warn');
    });
    
    socket.on('disconnect', (reason) => {
        realtimeConnected = false;
        updateEnvStatusConnection();
        if (reason !== 'io client disconnect') {
            writeLog('WebSocket 连接断开（' + reason + '），将自动重连', 'warn');
        }
    });
    
    socket.on('task_progress', (data) => {
        if (data.progress !== undefined) updateProgress(data.progress, data.message);
    });
    
    socket.on('task_complete', (data) => {
        hideProgress();
        if (data.success) {
            writeLog(data.message, 'ok');
        } else {
            writeLog(data.message, 'err');
        }
    });
    
    socket.on('error_diagnosis', (data) => {
        showErrorCard(data.error, data.diagnosis);
    });
    
    socket.on('connected', (data) => {
        writeLog(data.msg, 'info');
    });

    socket.on('reconnect_attempt', (attempt) => {
        writeLog('WebSocket 第 ' + attempt + ' 次重连尝试...', 'info');
    });
}

// ============ API 辅助 ============
async function parseApiResponse(res, url = '') {
    const text = await res.text();
    let data = null;
    try {
        data = text ? JSON.parse(text) : {};
    } catch(e) {
        const brief = text.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 220);
        throw new Error(`后端返回了非JSON错误页：${brief || res.status + ' ' + res.statusText}。接口：${url}`);
    }
    if (!res.ok) {
        throw new Error(data.error || data.message || `请求失败：HTTP ${res.status}`);
    }
    return data;
}

// escHtml 已移至 utils.js（通用辅助函数）

/**
 * ModuleTask - 统一管理功能模块的 UI 状态、进度和执行流程
 * 
 * 用法：
 *   const rebootTask = new ModuleTask('toolbox', '重启设备');
 *   rebootTask.confirm('确认重启设备到 fastboot 模式？', async () => {
 *       await rebootTask.execFastboot(['reboot', 'bootloader']);
 *   });
 */
class ModuleTask {
    constructor(module, label) {
        this.module = module;      // 模块名（对应 setModuleStatus 的第一个参数）
        this.label = label;       // 功能标签（用于日志和状态显示）
    }

    /** 设置模块状态 */
    status(msg, type = '') {
        setModuleStatus(this.module, `${this.label}状态：${msg}`, type);
    }

    /** 显示进度条 */
    showProgress(label) {
        showModuleProgress(this.module, label || this.label);
    }

    /** 更新进度 */
    updateProgress(percent, label) {
        updateModuleProgress(this.module, percent, label);
    }

    /** 隐藏进度条 */
    hideProgress() {
        hideModuleProgress(this.module);
    }

    /** 写日志 */
    log(msg, type = 'normal') {
        writeLog(`[${this.label}] ${msg}`, type);
    }

    /** 确认弹窗 + 执行 */
    async confirm(title, content, fn) {
        showConfirm(title, content, async () => {
            try {
                await fn();
            } catch(e) {
                this.hideProgress();
                this.status(`失败：${e.message}`, 'err');
                this.log(e.message, 'err');
            }
        });
    }

    /** 执行 fastboot 命令（自动选择 WebUSB 或后端） */
    async execFastboot(args, options = {}) {
        if (appRunMode === 'webusb' && webusbFastbootReady) {
            // WebUSB 模式
            return await webusbFastboot.fastbootCommand(args.join(' '));
        } else {
            // 后端模式
            const res = await apiPost('/api/fastboot/exec', { args: args });
            if (!res.success) throw new Error(res.error || '命令执行失败');
            return res;
        }
    }

    /** 执行擦除操作（含 AB 分区 fallback） */
    async erasePartition(part, options = {}) {
        this.log(`擦除分区：${part}`);
        try {
            await this.execFastboot(['erase', part]);
            this.log(`擦除 ${part} 完成`, 'ok');
            return true;
        } catch(e) {
            // 如果是 AB 设备且分区名不含 _a/_b 后缀，尝试添加
            if (isAbDevice && !part.endsWith('_a') && !part.endsWith('_b')) {
                this.log(`尝试擦除 ${part}_a ...`);
                try {
                    await this.execFastboot(['erase', part + '_a']);
                    await this.execFastboot(['erase', part + '_b']);
                    this.log(`擦除 ${part}_a + ${part}_b 完成`, 'ok');
                    return true;
                } catch(e2) {
                    throw e2;
                }
            }
            throw e;
        }
    }
}

async function apiGet(u) {
    const baseUrl = App.backendUrl || '';
    return await parseApiResponse(await fetch(baseUrl + u), u);
}

async function apiPost(u, d) {
    const baseUrl = App.backendUrl || '';
    return await parseApiResponse(await fetch(baseUrl + u, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(d)
    }), u);
}