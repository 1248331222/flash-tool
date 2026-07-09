// flash_tool/static/js/state.js
// ============ 应用状态（集中管理） ============
let _savedMode;
try { _savedMode = localStorage.getItem('run_mode'); } catch(e) { _savedMode = null; }
const App = {
    // 连接状态
    socket: null,
    backendReady: false,
    realtimeConnected: false,
    appRunMode: _savedMode || 'backend',
    backendUrl: '',
    envStatusBaseText: '正在连接后端服务...',
    envStatusBaseClass: 'env-status',

    // 设备状态
    deviceConnected: false,
    deviceMode: 'none',
    canAdb: false,
    canFastboot: false,
    currentSlot: '',
    isAbDevice: false,
    blUnlocked: null,
    blStatusText: 'Bootloader状态：未查询',
    deviceInfo: {},

    // WebUSB
    webusbAdb: null,
    webusbAdbReady: false,
    webusbFastboot: null,
    webusbFastbootReady: false,
    webusbScriptBaseDir: '',
    webusbScriptFileMap: new Map(),

    // 线刷任务
    stepList: [],
    customPartList: [],
    pendingResumeIndex: 0,

    // UI 状态
    wakeLock: null,
    confirmTimer: null,
    pageLogBoxes: {},

    // ============ 事件系统 ============
    /**
     * 轻量级发布/订阅事件总线，用于模块间一对多广播。
     * 支持 on/off/once/emit 四种操作，与 Node.js EventEmitter 语义相近。
     * @namespace App.event
     */
    event: {
        _listeners: {},

        /**
         * 订阅指定事件。
         * @param {string} evt - 事件名。
         * @param {function} fn - 事件触发时执行的回调。
         * @returns {Object} 事件总线自身，支持链式调用。
         */
        on(evt, fn) {
            if (!this._listeners[evt]) this._listeners[evt] = [];
            this._listeners[evt].push(fn);
            return this;
        },
        /**
         * 取消订阅指定事件。
         * @param {string} evt - 事件名。
         * @param {function} fn - 要移除的回调引用。
         * @returns {Object} 事件总线自身，支持链式调用。
         */
        off(evt, fn) {
            const list = this._listeners[evt];
            if (!list) return this;
            this._listeners[evt] = list.filter(f => f !== fn);
            return this;
        },

        /**
         * 一次性订阅：回调执行一次后自动取消订阅。
         * @param {string} evt - 事件名。
         * @param {function} fn - 事件触发时执行的回调。
         * @returns {Object} 事件总线自身，支持链式调用。
         */
        once(evt, fn) {
            const wrapper = (...args) => { fn(...args); this.off(evt, wrapper); };
            return this.on(evt, wrapper);
        },

        /**
         * 触发指定事件，同步调用所有订阅者。
         * @param {string} evt - 事件名。
         * @param {...*} args - 传递给订阅回调的参数。
         * @returns {Object} 事件总线自身，支持链式调用。
         */
        emit(evt, ...args) {
            (this._listeners[evt] || []).forEach(fn => fn(...args));
            return this;
        }
    },

    // ============ 重构新增：状态订阅系统（渐进采用） ============
    _subscribers: {},

    /**
     * 读取应用状态。
     * 支持点分路径（如 'deviceInfo.product'）；不传参数返回 App 自身。
     * @param {string} [key] - 状态键名或点分路径。
     * @returns {*} 对应状态的当前值。
     */
    get(key) {
        if (key === undefined) return this;
        return this._getPath(key);
    },
    _getPath(key) {
        if (typeof key !== 'string' || key.indexOf('.') === -1) return this[key];
        const parts = key.split('.');
        let cur = this;
        for (const p of parts) {
            if (cur == null || typeof cur !== 'object') return undefined;
            cur = cur[p];
        }
        return cur;
    },
    _setPath(key, value) {
        if (typeof key !== 'string' || key.indexOf('.') === -1) {
            this[key] = value;
            return;
        }
        const parts = key.split('.');
        let cur = this;
        for (let i = 0; i < parts.length - 1; i++) {
            const p = parts[i];
            if (!cur[p] || typeof cur[p] !== 'object') cur[p] = {};
            cur = cur[p];
        }
        cur[parts[parts.length - 1]] = value;
    },
    _notify(key, value, oldValue) {
        (this._subscribers[key] || []).forEach(fn => {
            try { fn(value, oldValue, key); } catch(e) { console.error('[App.set] 订阅者执行失败:', e); }
        });
    },
    /**
     * 设置应用状态并通知所有订阅者。
     * 支持点分路径；设置成功后会触发对应 key 的订阅回调（含新旧值）。
     * @param {string} key - 状态键名或点分路径。
     * @param {*} value - 要设置的新值。
     * @returns {Object} App 自身，支持链式调用。
     */
    set(key, value) {
        const oldValue = this._getPath(key);
        this._setPath(key, value);
        this._notify(key, value, oldValue);
        return this;
    },

    /**
     * 订阅指定状态的变化。
     * 注册时会立即以当前值执行一次回调，便于初始化同步。
     * @param {string} key - 状态键名或点分路径。
     * @param {function(*, *, string): void} fn - 回调参数为新值、旧值、键名。
     * @returns {function} 取消订阅的函数。
     */
    subscribe(key, fn) {
        if (!this._subscribers[key]) this._subscribers[key] = [];
        this._subscribers[key].push(fn);
        // 立即触发一次，让订阅者获得当前值
        try { fn(this._getPath(key), undefined, key); } catch(e) { console.error('[App.subscribe] 初始回调失败:', e); }
        return () => {
            this._subscribers[key] = this._subscribers[key].filter(f => f !== fn);
        };
    },
    /**
     * 通过 action 对象批量更新应用状态。
     * 内置 DEVICE_STATUS/RUN_MODE/STEP_LIST/BACKEND_READY/PROGRESS 等标准 action 类型，
     * 未知类型会回退为 App.set(type, payload)。
     * @param {Object} action - 必须包含 type 字段的动作对象。
     * @param {string} action.type - 动作类型。
     * @param {*} [action.payload] - 动作载荷。
     * @returns {Object} App 自身，支持链式调用。
     */
    dispatch(action) {
        if (!action || !action.type) {
            console.warn('[App.dispatch] action 必须包含 type 字段');
            return this;
        }
        const { type, payload } = action;
        switch (type) {
            case 'DEVICE_STATUS':
                if (payload.connected !== undefined) this.set('deviceConnected', payload.connected);
                if (payload.mode !== undefined) this.set('deviceMode', payload.mode);
                if (payload.canAdb !== undefined) this.set('canAdb', payload.canAdb);
                if (payload.canFastboot !== undefined) this.set('canFastboot', payload.canFastboot);
                if (payload.currentSlot !== undefined) this.set('currentSlot', payload.currentSlot);
                if (payload.isAbDevice !== undefined) this.set('isAbDevice', payload.isAbDevice);
                if (payload.blUnlocked !== undefined) this.set('blUnlocked', payload.blUnlocked);
                if (payload.blStatusText !== undefined) this.set('blStatusText', payload.blStatusText);
                if (payload.deviceInfo !== undefined) this.set('deviceInfo', payload.deviceInfo);
                break;
            case 'RUN_MODE':
                this.set('appRunMode', payload);
                break;
            case 'STEP_LIST':
                this.set('stepList', payload);
                break;
            case 'BACKEND_READY':
                this.set('backendReady', payload);
                break;
            case 'PROGRESS':
                this.set('progress', payload);
                break;
            default:
                this.set(type, payload);
        }
        return this;
    }
};

// 便捷访问别名（保持向后兼容，后续可逐步迁移）
// 使用 SafeDOM 获取，即使元素不存在也不会抛错
let logBox, envStatusEl, stepListEl, batchTip, progressContainer, progressBar, progressText, progressLabel;

/**
 * 双向同步别名：将全局 window 上的旧变量名映射到 App 状态的 getter/setter。
 * 读取时返回 App 中对应字段；写入时通过 App.set 更新并触发订阅。
 * 该机制保证旧代码无需改动即可兼容新的集中式状态管理。
 */
['socket','stepList','customPartList','deviceConnected','backendReady',
 'deviceMode','canAdb','canFastboot','appRunMode','currentSlot','isAbDevice',
 'blUnlocked','blStatusText','deviceInfo','pendingResumeIndex','wakeLock',
 'confirmTimer','pageLogBoxes','realtimeConnected','envStatusBaseText',
 'envStatusBaseClass','webusbAdb','webusbAdbReady','webusbFastboot',
 'webusbFastbootReady','webusbScriptBaseDir','webusbScriptFileMap'
].forEach(key => {
    Object.defineProperty(window, key, {
        get() { return App[key]; },
        set(v) { App.set(key, v); },
        enumerable: true, configurable: true
    });
});

// 兼容别名：BACKEND_API_URL → App.backendUrl
Object.defineProperty(window, 'BACKEND_API_URL', {
    get() { return App.backendUrl; },
    set(v) { App.set('backendUrl', v); },
    enumerable: true, configurable: true
});

// ============ 工作台状态变量 ============
let wbSteps = [];
let wbExecuting = false;
let wbDetectedPartitions = [];

// 步骤类型切换（按钮模式）
let wbCurrentType = 'fastboot';

// ============ 线刷批量任务状态变量 ============
let batchRunning = false;
let batchPaused = false;
let batchCurrentIndex = 0;
let batchTaskId = null;
let selectedUsbDevice = null;
let romImageCache = {};

// ============ 模块初始化 ============
Modules.register('state', [], function initStateModule() {
    logBox = $('logBox');
    envStatusEl = $('envStatus');
    stepListEl = $('stepList');
    batchTip = $('batchTip');
    progressContainer = $('progressContainer');
    progressBar = $('progressBar');
    progressText = $('progressText');
    progressLabel = $('progressLabel');

    console.log('[state] 应用状态模块已初始化');
    return true;
});