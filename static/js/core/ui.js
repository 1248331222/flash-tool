// flash_tool/static/js/ui.js
// ============ 进度条 ============
/**
 * 显示全局任务进度条并初始化进度为 0%。
 * @param {string} [label='任务进度'] - 进度条上方显示的标题文本。
 */
function showProgress(label = '任务进度') {
    progressContainer.style.display = 'block';
    progressLabel.textContent = label;
    progressBar.style.width = '0%';
    progressText.textContent = '0%';
}

/**
 * 更新全局任务进度条的百分比和提示文本。
 * @param {number} percent - 进度百分比（0-100）。
 * @param {string} [message] - 进度提示文本，最多显示 30 个字符。
 */
function updateProgress(percent, message) {
    progressBar.style.width = percent + '%';
    progressText.textContent = percent + '%';
    if (message) {
        progressLabel.textContent = message.substring(0, 30);
    }
}

/**
 * 隐藏全局任务进度条。
 */
function hideProgress() {
    progressContainer.style.display = 'none';
}

/**
 * 设置指定模块的状态文本和样式类。
 * @param {string} module - 模块标识，用于拼接 `${module}Status` 元素 id。
 * @param {string} message - 状态文本。
 * @param {string} [type='info'] - 状态类型（ok/warn/err/info 等）。
 */
function setModuleStatus(module, message, type = 'info') {
    const el = document.getElementById(`${module}Status`);
    if (!el) return;
    el.className = `module-status ${type}`;
    el.textContent = message;
}

/**
 * 显示指定模块的独立进度条。
 * @param {string} module - 模块标识，用于拼接 `${module}Progress` 元素 id。
 * @param {string} [label='准备中'] - 进度条初始标签。
 */
function showModuleProgress(module, label = '准备中') {
    const box = document.getElementById(`${module}Progress`);
    if (!box) return;
    box.style.display = 'block';
    updateModuleProgress(module, 0, label);
}

/**
 * 更新指定模块独立进度条的百分比和标签。
 * @param {string} module - 模块标识。
 * @param {number} percent - 进度百分比。
 * @param {string} [label=''] - 进度标签。
 */
function updateModuleProgress(module, percent, label = '') {
    const box = document.getElementById(`${module}Progress`);
    if (!box) return;
    const bar = box.querySelector('.module-progress-bar');
    const text = box.querySelector('.module-progress-text');
    const safe = Math.max(0, Math.min(100, Number(percent) || 0));
    if (bar) bar.style.width = `${safe}%`;
    if (text) text.textContent = label ? `${safe}% · ${label}` : `${safe}%`;
}

/**
 * 隐藏指定模块的独立进度条。
 * @param {string} module - 模块标识。
 */
function hideModuleProgress(module) {
    const box = document.getElementById(`${module}Progress`);
    if (box) box.style.display = 'none';
}

// ============ 主题切换 ============
/**
 * 切换页面主题：light / dark 两种模式循环切换，并持久化到 localStorage。
 */
function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);

    const btn = $('themeToggle');
    if (btn && btn.textContent !== undefined) {
        btn.textContent = next === 'light' ? '☀️' : '🌙';
    }

    localStorage.setItem('theme', next);
}

/**
 * 初始化页面主题：优先使用 localStorage 中保存的主题；
 * 若未保存，则根据北京时间 07:00-22:00 自动选择白天/夜间模式。
 */
function initTheme() {
    let saved = localStorage.getItem('theme');
    if (!saved) {
        // 根据北京时间判断：07:00-22:00 白天模式，其余夜间模式
        const now = new Date();
        const utcH = now.getUTCHours();
        const beijingH = (utcH + 8) % 24;
        saved = (beijingH >= 7 && beijingH < 22) ? 'light' : 'dark';
    }
    document.documentElement.setAttribute('data-theme', saved);
    const themeToggle = $('themeToggle');
    if (themeToggle && themeToggle.textContent !== undefined) {
        themeToggle.textContent = saved === 'light' ? '☀️' : '🌙';
    }
}

// ============ 帮助折叠 ============
function toggleHelp(id) {
    document.getElementById(id).classList.toggle('show');
}

// ============ 日志 ============
function getActiveViewName() {
    const active = document.querySelector('.app-view.active');
    return active ? active.dataset.view : (localStorage.getItem('active_view') || 'device');
}

function updateToolCurrentSlotBadge() {
    const el = document.getElementById('toolCurrentSlot');
    if (el) {
        el.textContent = `当前槽位：${currentSlot ? currentSlot.toUpperCase() : '未知'}`;
    }
    const slotBadge = document.getElementById('slotBadge');
    if (slotBadge) {
        if (currentSlot) {
            slotBadge.style.display = 'inline-block';
            slotBadge.textContent = `当前槽位：${currentSlot.toUpperCase()}`;
        } else {
            slotBadge.style.display = 'none';
        }
    }
}

function updateToolBlStatusBadge() {
    const el = document.getElementById('toolBlStatus');
    if (!el) return;
    el.classList.remove('ok', 'warn');
    if (blUnlocked === true) {
        el.textContent = 'Bootloader锁状态：已解锁';
        el.classList.add('ok');
    } else if (blUnlocked === false) {
        el.textContent = 'Bootloader锁状态：未解锁';
        el.classList.add('warn');
    } else {
        el.textContent = 'Bootloader锁状态：未知';
    }
}

function ensurePageLogBoxes() {
    // 只保留单一运行日志，不再创建线刷/单刷/工具/命令的分类日志框。
    if (pageLogBoxes.device) return;
    pageLogBoxes.device = logBox;
}

function getLogBoxForView(view = '') {
    ensurePageLogBoxes();
    return logBox;
}

/**
 * 非阻塞 Toast 提示，自动在页面顶部居中显示并在指定时间后消失。
 * @param {string} msg - 提示文本。
 * @param {number} [duration=3000] - 显示时长（毫秒）。
 */
function showToast(msg, duration = 3000) {
    const t = document.createElement('div');
    t.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);z-index:99999;background:rgba(0,0,0,0.85);color:#fff;padding:10px 20px;border-radius:8px;font-size:14px;max-width:80vw;text-align:center;pointer-events:auto;animation:toastIn 0.3s ease';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => {
        t.style.animation = 'toastOut 0.3s ease forwards';
        setTimeout(() => t.remove(), 300);
    }, duration);
}

const MAX_LOG_LINES = 2000;

/**
 * 向当前视图日志框追加一条带时间戳的日志。
 * 自动按类型添加前缀和样式，并维持日志行数上限（默认 2000 行）。
 * @param {string} msg - 日志内容。
 * @param {string} [type='normal'] - 日志类型（err/ok/tip/info/normal 等）。
 */
function writeLog(msg, type = 'normal') {
    const target = getLogBoxForView();
    const t = new Date().toLocaleTimeString();
    let pre = '';
    let cls = '';
    
    if (type === 'err') { pre = '[错误] '; cls = 'err-line'; }
    if (type === 'ok') { pre = '[成功] '; cls = 'ok-line'; }
    if (type === 'tip') { pre = '[提示] '; cls = 'tip-line'; }
    if (type === 'info') { pre = '[信息] '; cls = 'info-line'; }
    
    const line = document.createElement('div');
    line.className = cls;
    line.textContent = `[${t}] ${pre}${msg}`;
    target.appendChild(line);
    
    // 日志上限：超出时移除最早的
    while (target.childElementCount > MAX_LOG_LINES) {
        target.removeChild(target.firstChild);
    }
    
    target.scrollTop = target.scrollHeight;
}

function clearLogForView(view = '') {
    getLogBoxForView(view).innerHTML = '';
}

async function copyLogForView(view = '') {
    const text = getLogBoxForView(view).innerText || '';
    try {
        await navigator.clipboard.writeText(text);
        writeLog('日志已复制到剪贴板', 'ok');
    } catch(e) {
        writeLog('复制日志失败：浏览器未授权剪贴板', 'err');
    }
}

function exportLogForView(view = '') {
    const box = getLogBoxForView(view);
    const viewName = view || getActiveViewName();
    const saved = localStorage.getItem('batch_progress') || '';
    const meta = [
        `导出时间：${new Date().toLocaleString()}`,
        `日志页面：${viewName}`,
        `运行模式：${appRunMode}`,
        `线刷项目：${getSelectedRomProject ? (getSelectedRomProject() || '未选择') : '未知'}`,
        `脚本：${document.getElementById('batSelect') ? (document.getElementById('batSelect').value || '未选择') : '未知'}`,
        `步骤数：${stepList.length}`,
        `设备代号：${getDeviceProduct()}`,
        `Fastboot模式：${getFastbootModeLabel ? getFastbootModeLabel() : '未知'}`,
        `槽位：${currentSlot || '未知'}`,
        `Bootloader：${blStatusText}`,
        `断点：${saved || '无'}`
    ].join('\n');
    const text = `${meta}\n\n===== 运行日志 =====\n${box.innerText}`;
    const blob = new Blob([text], {type: 'text/plain'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `刷机日志_${viewName}_${new Date().toLocaleDateString().replace(/\//g,'-')}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    writeLog('日志已导出到下载目录', 'ok');
}

// ============ 确认弹窗 ============
/**
 * 显示带 3 秒倒计时的确认弹窗，用户确认后执行回调。
 * @param {string} title - 弹窗标题。
 * @param {string} content - 弹窗内容文本。
 * @param {function} onOk - 用户点击确认后执行的回调（支持异步）。
 * @param {boolean} [danger=true] - 是否使用危险（红色）样式按钮。
 */
function showConfirm(title, content, onOk, danger = true) {
    document.getElementById('confirmTitle').textContent = title;
    document.getElementById('confirmContent').textContent = content;
    
    const okBtn = document.getElementById('confirmOkBtn');
    okBtn.className = danger ? 'btn danger small' : 'btn small';
    okBtn.disabled = true;
    
    let count = 3;
    okBtn.textContent = `确认(${count})`;
    
    clearInterval(confirmTimer);
    confirmTimer = setInterval(() => {
        count--;
        if (count <= 0) {
            clearInterval(confirmTimer);
            okBtn.disabled = false;
            okBtn.textContent = '确认';
        } else {
            okBtn.textContent = `确认(${count})`;
        }
    }, 1000);
    
    document.getElementById('confirmModal').classList.add('show');
    
    okBtn.onclick = async () => {
        document.getElementById('confirmModal').classList.remove('show');
        clearInterval(confirmTimer);
        try {
            if (onOk) await onOk();
        } catch(e) {
            writeLog('操作失败: ' + e.message, 'err');
        }
    };
    
    document.getElementById('confirmCancelBtn').onclick = () => {
        document.getElementById('confirmModal').classList.remove('show');
        clearInterval(confirmTimer);
    };
}

function startFlashFromIndex(index = 0) {
    pendingResumeIndex = Number(index) || 0;
    document.getElementById('batchFlashBtn').click();
}

// ============ 屏幕常亮 ============
async function requestWakeLock() {
    try {
        if ('wakeLock' in navigator) {
            wakeLock = await navigator.wakeLock.request('screen');
            writeLog('屏幕常亮已启用', 'info');
        }
    } catch(e) {}
}

async function releaseWakeLock() {
    if (wakeLock) {
        try { await wakeLock.release(); } catch(e) {}
        wakeLock = null;
        writeLog('屏幕常亮已关闭', 'info');
    }
}

// ============ 补充函数 ============
function updateSmartUI() {
    const modeName = appRunMode === 'webusb' ? 'WebUSB' : '后端';
    let conn = '未连接设备';
    if (webusbFastbootReady || deviceMode === 'webusb-fastboot' || canFastboot) conn = `${getFastbootModeLabel()}已连接`;
    else if (webusbAdbReady || deviceMode === 'webusb-adb' || canAdb) conn = 'ADB已连接';
    const slot = currentSlot ? ` · 槽位${currentSlot.toUpperCase()}` : '';
    const bl = blUnlocked === true ? ' · Bootloader已解锁' : (blUnlocked === false ? ' · Bootloader未解锁' : '');
    document.getElementById('globalStatusText').textContent = `${modeName} · ${conn}${slot}${bl}`;

    const title = document.getElementById('smartNextTitle');
    const text = document.getElementById('smartNextText');
    const actions = document.getElementById('smartNextActions');
    if (!canAdb && !canFastboot && !webusbAdbReady && !webusbFastbootReady) {
        title.textContent = '下一步：连接设备';
        text.textContent = '请选择连接模式，然后点击检测设备。';
        actions.innerHTML = '<button class="btn small" data-action="check-device">检测设备</button>';
    } else if (canAdb && !canFastboot && !webusbFastbootReady) {
        title.textContent = '下一步：进入Bootloader';
        text.textContent = '当前可用 ADB。如需刷机，请先重启到 Bootloader/Fastboot。';
        actions.innerHTML = '<button class="btn small" data-action="reboot-bootloader">重启Bootloader</button>';
    } else {
        title.textContent = '下一步：选择刷写任务';
        text.textContent = '设备已处于可刷写状态，可以导入线刷脚本或进行单分区刷写。';
        actions.innerHTML = '<button class="btn small" data-action="switch-view" data-view="batch">去线刷</button><button class="btn secondary small" data-action="switch-view" data-view="single">去单刷</button>';
    }
}

function updateSafetySummaryLine() {
    const el = document.getElementById('safetySummaryLine');
    if (!el) return;
    const fastbootReady = canFastboot || webusbFastbootReady;
    const device = fastbootReady ? `${getFastbootModeLabel()}已连` : (canAdb || webusbAdbReady ? 'ADB已连' : '设备未就绪');
    const bl = blUnlocked === true ? 'Bootloader已解锁' : (blUnlocked === false ? 'Bootloader未解锁' : 'Bootloader未查询');
    const r = stepList.length ? analyzeScriptRisks() : {highRisk: [], wipesData: false, locksBl: false};
    const script = stepList.length ? `${stepList.length}步` : '未解析脚本';
    const risk = stepList.length ? `高危${r.highRisk.length}${r.wipesData ? ' · 清数据' : ''}${r.locksBl ? ' · 含上锁' : ''}` : '';
    el.textContent = [device, bl, script, risk].filter(Boolean).join(' · ');
}

/* updateResumeCard 定义在 bat_risk.js 中，此处复用不重复定义 */

/* updatePrecheckSummary 定义在 bat_risk.js 中，此处复用不重复定义 */

function fillCommandTemplate(tool, command) {
    // 兼容旧命令页和工作台
    const toolEl = document.getElementById('commandTool');
    const cmdEl = document.getElementById('customFastbootCmd');
    if (toolEl) toolEl.value = tool;
    if (cmdEl) cmdEl.value = command;
    setModuleStatus('command', `命令模板已填入：${tool} ${command}`, 'info');
}

function toggleModeDetail() {
    const detail = document.getElementById('modeDetail');
    const btn = document.querySelector('.mode-more');
    detail.classList.toggle('show');
    btn.textContent = detail.classList.contains('show') ? '收起说明 ▴' : '模式说明 ▾';
}

function setRunMode(mode) {
    App.set('appRunMode', mode);
    localStorage.setItem('run_mode', mode);
    document.body.setAttribute('data-run-mode', mode);
    document.getElementById('backendModeCard').classList.toggle('active', mode === 'backend');
    document.getElementById('webusbModeCard').classList.toggle('active', mode === 'webusb');
    if (mode === 'backend') {
        setModuleStatus('mode', '当前模式：后端模式', 'ok');
        const _ct = document.getElementById('commandTool'); if(_ct) _ct.value = canFastboot ? 'fastboot' : 'adb';
    } else {
        setModuleStatus('mode', '当前模式：WebUSB模式', 'warn');
        const _ct2 = document.getElementById('commandTool'); if(_ct2) _ct2.value = 'adb';
    }
    updateBtnState();
}

function updateModeFeatureState() {
    const webusb = appRunMode === 'webusb';
    const batchBtn = $('batchFlashBtn');
    if (webusb) {
        batchBtn.title = 'WebUSB模式已禁用线刷，避免大镜像占满浏览器内存导致主设备卡死';
        setModuleStatus('batch', '线刷状态：WebUSB模式不支持线刷。请切换到后端模式执行完整线刷；WebUSB仅建议用于命令和单分区刷写。', 'warn');
        setModuleStatus('single', '单分区刷写状态：WebUSB模式已启用。请先检测 WebUSB Fastboot 设备。', 'warn');
    } else {
        batchBtn.title = '';
        if (stepList.length === 0) setModuleStatus('batch', '线刷状态：等待解析脚本并检测设备。', 'info');
        if (customPartList.length === 0) setModuleStatus('single', '单分区刷写状态：等待添加刷写任务。', 'info');
    }
}

// ============ 通用 data-action 事件委托 ============
function handleGlobalAction(e) {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const action = btn.dataset.action;

    switch (action) {
        case 'theme-toggle':
            e.preventDefault();
            toggleTheme();
            break;
        case 'toggle-help':
            e.preventDefault();
            toggleHelp(btn.dataset.target);
            break;
        case 'toggle-mode-detail':
            e.preventDefault();
            toggleModeDetail();
            break;
        case 'set-run-mode':
            e.preventDefault();
            setRunMode(btn.dataset.mode);
            break;
        case 'check-device':
            e.preventDefault();
            {
                const checkBtn = $('checkDeviceBtn');
                if (checkBtn) checkBtn.click();
            }
            break;
        case 'query-slot':
            e.preventDefault();
            {
                const queryBtn = $('querySlotBtn');
                if (queryBtn) queryBtn.click();
            }
            break;
        case 'switch-view':
            e.preventDefault();
            switchAppView(btn.dataset.view);
            break;
        case 'open-upload-dialog':
            e.preventDefault();
            if (typeof openUploadDialog === 'function') openUploadDialog();
            break;
        case 'close-upload-dialog':
            e.preventDefault();
            if (typeof closeUploadDialog === 'function') closeUploadDialog();
            break;
        case 'upload-select-file':
            e.preventDefault();
            {
                const input = $('uploadFileInput');
                if (input) input.click();
            }
            break;
        case 'upload-submit':
            e.preventDefault();
            if (typeof submitUpload === 'function') submitUpload();
            break;
        case 'refresh-upload-list':
            e.preventDefault();
            if (typeof refreshUploadList === 'function') refreshUploadList();
            break;
        case 'quick-upload-script':
            e.preventDefault();
            if (typeof quickUploadScript === 'function') quickUploadScript();
            break;
        case 'copy-bat-source':
            e.preventDefault();
            e.stopPropagation();
            if (typeof copyBatSource === 'function') copyBatSource();
            break;
        case 'use-native-sh':
            e.preventDefault();
            if (typeof useNativeShScript === 'function') useNativeShScript();
            break;
        case 'use-custom-script':
            e.preventDefault();
            if (typeof useCustomScript === 'function') useCustomScript();
            break;
        case 'cancel-custom-script':
            e.preventDefault();
            if (typeof cancelCustomScript === 'function') cancelCustomScript();
            break;
        case 'reboot-bootloader':
            e.preventDefault();
            {
                const rbBtn = $('rebootBootloaderBtn');
                if (rbBtn) rbBtn.click();
            }
            break;
    }
}

// ============ 模块初始化 ============
Modules.register('ui', [], function initUIModule() {
    initTheme();

    // 日志按钮绑定
    $('clearLogBtn').onclick = () => clearLogForView('device');
    $('exportLogBtn').onclick = () => exportLogForView('device');

    // document.body 级别通用事件委托
    document.body.addEventListener('click', handleGlobalAction);

    // 状态订阅：设备/模式变化自动驱动 UI 更新。
    // 使用 setTimeout 推迟到当前同步加载流程结束后注册，避免 ui.js 早于
    // device_info.js / bat_risk.js / custom_flash.js 执行时回调函数未定义。
    setTimeout(() => {
        App.subscribe('deviceConnected', updateBtnState);
        App.subscribe('canFastboot', updateBtnState);
        App.subscribe('canAdb', updateBtnState);
        App.subscribe('appRunMode', updateModeFeatureState);
        App.subscribe('currentSlot', updateToolCurrentSlotBadge);
        App.subscribe('blUnlocked', updateToolBlStatusBadge);
        App.subscribe('backendReady', updateEnvStatusConnection);
        // deviceInfo 变更后更新信息摘要（该函数在 flash.js 中定义，用延迟引用避免加载顺序问题）
        App.subscribe('deviceInfo', () => {
            if (typeof updateDeviceInfoSummary === 'function') updateDeviceInfoSummary();
        });
    }, 0);

    return true;
});
