// flash_tool/static/js/ui.js
// ============ 进度条 ============
function showProgress(label = '任务进度') {
    progressContainer.style.display = 'block';
    progressLabel.textContent = label;
    progressBar.style.width = '0%';
    progressText.textContent = '0%';
}

function updateProgress(percent, message) {
    progressBar.style.width = percent + '%';
    progressText.textContent = percent + '%';
    if (message) {
        progressLabel.textContent = message.substring(0, 30);
    }
}

function hideProgress() {
    progressContainer.style.display = 'none';
}

function setModuleStatus(module, message, type = 'info') {
    const el = document.getElementById(`${module}Status`);
    if (!el) return;
    el.className = `module-status ${type}`;
    el.textContent = message;
}

function showModuleProgress(module, label = '准备中') {
    const box = document.getElementById(`${module}Progress`);
    if (!box) return;
    box.style.display = 'block';
    updateModuleProgress(module, 0, label);
}

function updateModuleProgress(module, percent, label = '') {
    const box = document.getElementById(`${module}Progress`);
    if (!box) return;
    const bar = box.querySelector('.module-progress-bar');
    const text = box.querySelector('.module-progress-text');
    const safe = Math.max(0, Math.min(100, Number(percent) || 0));
    if (bar) bar.style.width = `${safe}%`;
    if (text) text.textContent = label ? `${safe}% · ${label}` : `${safe}%`;
}

function hideModuleProgress(module) {
    const box = document.getElementById(`${module}Progress`);
    if (box) box.style.display = 'none';
}

// ============ 主题切换 ============
function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    
    const btn = document.getElementById('themeToggle');
    btn.textContent = next === 'light' ? '☀️' : '🌙';
    
    localStorage.setItem('theme', next);
}

// 初始化主题（优先 localStorage，其次根据北京时间自动判断）
(function() {
    let saved = localStorage.getItem('theme');
    if (!saved) {
        // 根据北京时间判断：07:00-22:00 白天模式，其余夜间模式
        const now = new Date();
        const utcH = now.getUTCHours();
        const beijingH = (utcH + 8) % 24;
        saved = (beijingH >= 7 && beijingH < 22) ? 'light' : 'dark';
    }
    document.documentElement.setAttribute('data-theme', saved);
    document.getElementById('themeToggle').textContent = saved === 'light' ? '☀️' : '🌙';
})();

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
    if (!el) return;
    el.textContent = `当前槽位：${currentSlot ? currentSlot.toUpperCase() : '未知'}`;
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

// 非阻塞 toast 提示（替代 alert）
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

document.getElementById('clearLogBtn').onclick = () => clearLogForView('device');

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

document.getElementById('exportLogBtn').onclick = () => exportLogForView('device');

// ============ 确认弹窗 ============
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
        actions.innerHTML = '<button class="btn small" onclick="document.getElementById(\'checkDeviceBtn\').click()">检测设备</button>';
    } else if (canAdb && !canFastboot && !webusbFastbootReady) {
        title.textContent = '下一步：进入Bootloader';
        text.textContent = '当前可用 ADB。如需刷机，请先重启到 Bootloader/Fastboot。';
        actions.innerHTML = '<button class="btn small" onclick="document.getElementById(\'rebootBootloaderBtn\').click()">重启Bootloader</button>';
    } else {
        title.textContent = '下一步：选择刷写任务';
        text.textContent = '设备已处于可刷写状态，可以导入线刷脚本或进行单分区刷写。';
        actions.innerHTML = '<button class="btn small" onclick="switchAppView(\'batch\')">去线刷</button><button class="btn secondary small" onclick="switchAppView(\'single\')">去单刷</button>';
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

function updateResumeCard() {
    const box = document.getElementById('resumeSummary');
    const text = document.getElementById('resumeText');
    if (!box || !text) return;
    const saved = localStorage.getItem('batch_progress');
    if (!saved) { box.style.display = 'none'; return; }
    try {
        const data = JSON.parse(saved);
        pendingResumeIndex = Number(data.step_index || 0);
        if (!data.steps || pendingResumeIndex <= 0) { box.style.display = 'none'; return; }
        box.style.display = 'block';
        const total = data.steps.length;
        const last = data.steps[Math.min(pendingResumeIndex, total - 1)] || {};
        text.textContent = `上次进度：第 ${pendingResumeIndex + 1} / ${total} 步，当前步骤：${last.raw || last.part || last.type || '未知'}。`;
    } catch(e) {
        box.style.display = 'none';
    }
}

function updatePrecheckSummary() {
    const text = document.getElementById('precheckText');
    const metrics = document.getElementById('precheckMetrics');
    if (!text || !metrics) return;
    const fastbootReady = canFastboot || webusbFastbootReady;
    const scriptReady = stepList.length > 0;
    const slot = currentSlot ? `槽位：${currentSlot.toUpperCase()}` : '槽位：未知';
    const deviceLabel = fastbootReady ? '设备：Fastboot已连接' : (canAdb || webusbAdbReady ? '设备：ADB已连接' : '设备：未就绪');
    const blLabel = blStatusText.replace('Bootloader状态：', 'Bootloader：').replace('。', '');
    metrics.innerHTML = `
        <span class="metric">${deviceLabel}</span>
        <span class="metric">${blLabel}</span>
        <span class="metric">${slot}</span>
        <span class="metric">脚本：${scriptReady ? stepList.length + '步' : '未解析'}</span>`;
    if (!fastbootReady) {
        text.textContent = '不能线刷：请先连接 Fastboot/Bootloader 设备。';
    } else if (blUnlocked === false) {
        text.textContent = '不建议线刷：Bootloader 未解锁，大多数分区刷写会失败。';
    } else if (!scriptReady) {
        text.textContent = '等待解析刷机脚本。';
    } else {
        text.textContent = '检查通过：设备和脚本已就绪，可以执行线刷。';
    }
    updateSafetySummaryLine();
}

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
    appRunMode = mode;
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
    updateModeFeatureState();
    updateBtnState();
}

function updateModeFeatureState() {
    const webusb = appRunMode === 'webusb';
    const batchBtn = document.getElementById('batchFlashBtn');
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
