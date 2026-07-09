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
    // 防止重复连接：如果已有活跃连接，不再创建新的
    if (socket && socket.connected) {
        return;
    }
    // 如果 socket 存在但已断开，清理掉重新创建
    if (socket) {
        socket.removeAllListeners();
        socket.close();
        socket = null;
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
        // 服务端连接确认（与 socket.on('connect') 不重复）
    });

    socket.on('reconnect_attempt', (attempt) => {
        writeLog('WebSocket 第 ' + attempt + ' 次重连尝试...', 'info');
    });
}

// ============ API 辅助 ============
/**
 * 解析后端 fetch 响应：先读取文本再按 JSON 解析，遇到非 JSON 错误页时抛出可读异常。
 * 当响应状态码非 2xx 时，优先取 data.error / data.message 作为错误信息。
 * @param {Response} res - fetch 返回的 Response 对象。
 * @param {string} [url=''] - 接口地址，用于错误信息定位。
 * @returns {Promise<Object>} 解析后的后端数据对象。
 * @throws {Error} 解析失败或 HTTP 错误时抛出异常。
 */
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
 * 统一管理功能模块的 UI 状态、进度和执行流程的封装类。
 * 典型用法：
 *   const rebootTask = new ModuleTask('toolbox', '重启设备');
 *   rebootTask.confirm('确认重启设备到 fastboot 模式？', async () => {
 *       await rebootTask.execFastboot(['reboot', 'bootloader']);
 *   });
 */
class ModuleTask {
    /**
     * 创建模块任务实例。
     * @param {string} module - 模块名（对应 setModuleStatus 的第一个参数）。
     * @param {string} label - 功能标签（用于日志和状态显示）。
     */
    constructor(module, label) {
        this.module = module;      // 模块名（对应 setModuleStatus 的第一个参数）
        this.label = label;       // 功能标签（用于日志和状态显示）
    }

    /**
     * 设置当前模块的状态文本和样式。
     * @param {string} msg - 状态文本。
     * @param {string} [type=''] - 状态类型（ok/warn/err/info 等）。
     */
    status(msg, type = '') {
        setModuleStatus(this.module, `${this.label}状态：${msg}`, type);
    }

    /**
     * 显示当前模块的进度条。
     * @param {string} [label] - 进度条标签，默认使用任务标签。
     */
    showProgress(label) {
        showModuleProgress(this.module, label || this.label);
    }

    /**
     * 更新当前模块的进度百分比。
     * @param {number} percent - 进度百分比（0-100）。
     * @param {string} [label] - 进度条标签。
     */
    updateProgress(percent, label) {
        updateModuleProgress(this.module, percent, label);
    }

    /**
     * 隐藏当前模块的进度条。
     */
    hideProgress() {
        hideModuleProgress(this.module);
    }

    /**
     * 向全局日志输出带标签的消息。
     * @param {string} msg - 日志内容。
     * @param {string} [type='normal'] - 日志类型（ok/err/warn/tip/info 等）。
     */
    log(msg, type = 'normal') {
        writeLog(`[${this.label}] ${msg}`, type);
    }

    /**
     * 弹出确认弹窗，用户确认后执行任务函数，并统一捕获异常。
     * @param {string} title - 弹窗标题。
     * @param {string} content - 弹窗内容。
     * @param {function} fn - 用户确认后执行的异步函数。
     */
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

    /**
     * 执行 fastboot 命令，根据当前运行模式自动选择 WebUSB 或后端。
     * @param {string[]} args - fastboot 子命令参数数组。
     * @param {Object} [options={}] - 执行选项（保留扩展用）。
     * @returns {Promise<*>} 命令执行结果。
     * @throws {Error} 命令执行失败时抛出异常。
     */
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

    /**
     * 执行分区擦除操作，失败时针对 AB 设备自动尝试 _a/_b 双槽位回退。
     * @param {string} part - 要擦除的分区名。
     * @param {Object} [options={}] - 执行选项（保留扩展用）。
     * @returns {Promise<boolean>} 擦除成功返回 true。
     * @throws {Error} 所有擦除尝试均失败时抛出异常。
     */
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

// ============ 统一 API 请求封装 ============
/**
 * 统一底层 API 请求封装，自动拼接后端地址、处理超时和 JSON 序列化。
 * 返回标准化对象 { ok, data/error }，不会抛出异常，便于调用方统一处理。
 * @param {string} url - 相对或绝对接口地址。
 * @param {Object} [options={}] - fetch 选项；支持自定义 timeout（毫秒）。
 * @returns {Promise<{ok: boolean, data?: *, error?: string}>} 标准化响应对象。
 */
async function apiRequest(url, options = {}) {
    const baseUrl = App.backendUrl || '';
    const fullUrl = baseUrl + url;
    const method = (options.method || 'GET').toUpperCase();
    const timeout = options.timeout !== undefined
        ? options.timeout
        : (method === 'POST' || options.body ? 30000 : 15000);

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);

    try {
        const fetchOptions = {
            ...options,
            method,
            signal: controller.signal
        };
        if (fetchOptions.body && typeof fetchOptions.body !== 'string') {
            fetchOptions.body = JSON.stringify(fetchOptions.body);
        }
        const res = await fetch(fullUrl, fetchOptions);
        const text = await res.text();
        let data = null;
        try {
            data = text ? JSON.parse(text) : {};
        } catch(e) {
            const brief = text.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 220);
            return { ok: false, error: `后端返回了非JSON错误页：${brief || res.status + ' ' + res.statusText}。接口：${url}` };
        }
        if (!res.ok) {
            return { ok: false, error: data.error || data.message || `请求失败：HTTP ${res.status}` };
        }
        return { ok: true, data };
    } catch(e) {
        if (e && e.name === 'AbortError') {
            return { ok: false, error: '请求超时' };
        }
        return { ok: false, error: e && e.message ? e.message : String(e) };
    } finally {
        clearTimeout(timer);
    }
}

/**
 * 封装 GET 请求，请求失败时直接抛出异常。
 * @param {string} url - 相对接口地址。
 * @param {Object} [options={}] - 额外 fetch 选项。
 * @returns {Promise<*>} 后端返回的数据对象。
 * @throws {Error} 请求失败时抛出异常。
 */
async function apiGet(url, options = {}) {
    const r = await apiRequest(url, { ...options, method: 'GET' });
    if (!r.ok) throw new Error(r.error);
    return r.data;
}

/**
 * 封装 POST 请求，自动设置 Content-Type: application/json，请求失败时抛出异常。
 * @param {string} url - 相对接口地址。
 * @param {Object} body - 请求体对象。
 * @param {Object} [options={}] - 额外 fetch 选项。
 * @returns {Promise<*>} 后端返回的数据对象。
 * @throws {Error} 请求失败时抛出异常。
 */
async function apiPost(url, body, options = {}) {
    const r = await apiRequest(url, {
        ...options,
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
        body
    });
    if (!r.ok) throw new Error(r.error);
    return r.data;
}

// 注册 API 模块：初始化时预检后端连通性（非阻塞）
Modules.register('api', [], async function initApiModule() {
    // 这里只做轻量级初始化，不阻塞其他模块
    console.log('[api] API 层已就绪（超时保护已启用）');
    return { apiRequest, apiGet, apiPost, parseApiResponse };
});