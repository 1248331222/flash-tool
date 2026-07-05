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
    // App.event.on('uploadListChanged', fn)  / App.event.emit('uploadListChanged', data)
    event: {
        _listeners: {},
        on(evt, fn) {
            if (!this._listeners[evt]) this._listeners[evt] = [];
            this._listeners[evt].push(fn);
            return this;
        },
        off(evt, fn) {
            const list = this._listeners[evt];
            if (!list) return this;
            this._listeners[evt] = list.filter(f => f !== fn);
            return this;
        },
        once(evt, fn) {
            const wrapper = (...args) => { fn(...args); this.off(evt, wrapper); };
            return this.on(evt, wrapper);
        },
        emit(evt, ...args) {
            (this._listeners[evt] || []).forEach(fn => fn(...args));
            return this;
        }
    },
};

// 便捷访问别名（保持向后兼容，后续可逐步迁移）
const logBox = document.getElementById('logBox');
const envStatusEl = document.getElementById('envStatus');
const stepListEl = document.getElementById('stepList');
const batchTip = document.getElementById('batchTip');
const progressContainer = document.getElementById('progressContainer');
const progressBar = document.getElementById('progressBar');
const progressText = document.getElementById('progressText');
const progressLabel = document.getElementById('progressLabel');

// 双向同步别名
['socket','stepList','customPartList','deviceConnected','backendReady',
 'deviceMode','canAdb','canFastboot','appRunMode','currentSlot','isAbDevice',
 'blUnlocked','blStatusText','deviceInfo','pendingResumeIndex','wakeLock',
 'confirmTimer','pageLogBoxes','realtimeConnected','envStatusBaseText',
 'envStatusBaseClass','webusbAdb','webusbAdbReady','webusbFastboot',
 'webusbFastbootReady','webusbScriptBaseDir','webusbScriptFileMap'
].forEach(key => {
    Object.defineProperty(window, key, {
        get() { return App[key]; },
        set(v) { App[key] = v; },
        enumerable: true, configurable: true
    });
});

// 兼容别名：BACKEND_API_URL → App.backendUrl
Object.defineProperty(window, 'BACKEND_API_URL', {
    get() { return App.backendUrl; },
    set(v) { App.backendUrl = v; },
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