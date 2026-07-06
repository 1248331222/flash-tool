// flash_tool/static/js/device_info.js
// ============ 补充函数 ============
function getFastbootModeLabel() {
    const raw = String(deviceInfo.is_userspace || deviceInfo['is-userspace'] || '').trim().toLowerCase();
    if (['yes', 'true', '1'].includes(raw)) return 'fastbootd';
    if (['no', 'false', '0'].includes(raw)) return 'Bootloader Fastboot';
    return 'Fastboot';
}

function cleanFastbootVarValue(v) {
    const s = String(v || '').trim().replace(/^['"]|['"]$/g, '');
    if (!s) return '';
    if (/^(finished\.|okay|failed|getvar:|waiting for)/i.test(s)) return '';
    return s;
}

function extractFastbootVar(text, varName) {
    const name = String(varName || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace('\\-', '[-_]');
    const reColon = new RegExp('^\\s*(?:\\(bootloader\\)\\s*)?' + name + '\\s*:\\s*(.+?)\\s*$', 'i');
    const reEq = new RegExp('^\\s*' + name + '\\s*=\\s*(.+?)\\s*$', 'i');
    for (const line of String(text || '').split(/\r?\n/)) {
        const clean = line.trim();
        if (!clean || /^(finished\.|okay|failed|waiting for|getvar:)/i.test(clean)) continue;
        const m = clean.match(reColon) || clean.match(reEq);
        if (m) {
            const val = cleanFastbootVarValue(m[1]);
            if (val) return val;
        }
    }
    return '';
}

function getDeviceProduct() {
    return cleanFastbootVarValue(deviceInfo.product_display)
        || cleanFastbootVarValue(deviceInfo.product)
        || cleanFastbootVarValue(deviceInfo.product_name)
        || '未知';
}

function yesNoText(v) {
    const s = String(v ?? '').trim().toLowerCase();
    if (['yes', 'true', '1', 'unlocked'].includes(s)) return '是';
    if (['no', 'false', '0', 'locked'].includes(s)) return '否';
    return v === undefined || v === null || v === '' ? '未知' : String(v);
}

function normalizeBatterySoc(v) {
    const s = cleanFastbootVarValue(v);
    if (!s) return '未知';
    return /^\d+$/.test(s) ? `${s}%` : s;
}

function normalizeVoltage(v) {
    const s = cleanFastbootVarValue(v);
    if (!s) return '未知';
    if (/^\d+$/.test(s)) {
        const n = Number(s);
        if (n > 1000) return `${(n / 1000).toFixed(2)}V`;
    }
    return s;
}

function formatDeviceInfoHuman(info = {}) {
    const product = cleanFastbootVarValue(info.product_display) || cleanFastbootVarValue(info.product) || getDeviceProduct();
    const productName = cleanFastbootVarValue(info.product_name);
    const slot = cleanFastbootVarValue(info.current_slot || currentSlot);
    const userspace = String(info.is_userspace || info['is-userspace'] || '').trim().toLowerCase();
    const mode = userspace === 'yes' || userspace === 'true' || userspace === '1' ? 'Fastbootd（用户空间）' : getFastbootModeLabel();
    const lines = [
        '设备信息读取成功：',
        `设备代号：${product || '未知'}`,
        productName && productName !== product ? `产品名称：${productName}` : '',
        `当前模式：${mode}`,
        `当前槽位：${slot ? slot.toUpperCase() : '未知'}`,
        `电池电量：${normalizeBatterySoc(info.battery_soc || info.battery)}`,
        `电池电压：${normalizeVoltage(info.battery_voltage)}`,
        `序列号：${cleanFastbootVarValue(info.serial) || '未知'}`,
        `Bootloader版本：${cleanFastbootVarValue(info.bootloader_version) || '未知'}`,
        `Fastboot版本：${cleanFastbootVarValue(info.fastboot_version) || '未知'}`,
        `是否Fastbootd：${yesNoText(info.is_userspace || info['is-userspace'])}`,
        `Bootloader状态：${blStatusText.replace('Bootloader状态：', '') || '未查询'}`
    ].filter(Boolean);
    return lines;
}

function writeDeviceInfoHumanLog(info = {}) {
    formatDeviceInfoHuman(info).forEach(line => writeLog(line, 'info'));
}

function updateBtnState() {
    const backendFastbootUsable = backendReady && canFastboot;
    const backendAdbUsable = backendReady && canAdb;
    const fastbootUsable = backendFastbootUsable || webusbFastbootReady;
    const adbUsable = backendAdbUsable || webusbAdbReady;
    const anyUsable = fastbootUsable || adbUsable;
    const backendMode = appRunMode === 'backend';
    const flashModeUsable = backendMode && backendFastbootUsable;
    const vbmetaUsable = appRunMode === 'webusb' ? webusbFastbootReady : backendFastbootUsable;
    document.getElementById('batchFlashBtn').disabled = !flashModeUsable || stepList.length === 0;
    document.getElementById('rebootSysBtn').disabled = !anyUsable;
    document.getElementById('rebootRecBtn').disabled = !anyUsable;
    document.getElementById('rebootFbBtn').disabled = !anyUsable;
    document.getElementById('rebootBootloaderBtn').disabled = !anyUsable;
    document.getElementById('readDeviceInfoBtn').disabled = !fastbootUsable;
    document.getElementById('querySlotBtn').disabled = !fastbootUsable;
    const _rcfb = document.getElementById('runCustomFastbootBtn'); if(_rcfb) _rcfb.disabled = !backendReady;
    document.getElementById('disableVbmetaBtn').disabled = !vbmetaUsable || !document.getElementById('vbmetaSelect').value;
    document.getElementById('setSlotBtn').disabled = !fastbootUsable;
    document.getElementById('wipeBtn').disabled = !fastbootUsable;
    document.getElementById('wipeMetadataBtn').disabled = !fastbootUsable;
    document.getElementById('checkBlBtn').disabled = !fastbootUsable;
    document.getElementById('unlockBlBtn').disabled = !fastbootUsable;
    document.getElementById('lockBlBtn').disabled = !fastbootUsable;
    document.getElementById('simulateBtn').disabled = stepList.length === 0;
    document.getElementById('clearBatchStepsBtn').disabled = stepList.length === 0;
    updateBatchActionState({fastbootUsable, adbUsable, anyUsable, flashModeUsable, backendMode});
    updateButtonHints({fastbootUsable, adbUsable, anyUsable, flashModeUsable, backendMode, vbmetaUsable});
    renderCustomList();
    updateSmartUI();
    updatePrecheckSummary();
}

function updateButtonHints(state = {}) {
    const backendFastbootUsable = backendReady && canFastboot;
    const fastbootUsable = state.fastbootUsable ?? (backendFastbootUsable || webusbFastbootReady);
    const anyUsable = state.anyUsable ?? (fastbootUsable || canAdb || webusbAdbReady);
    const backendMode = state.backendMode ?? (appRunMode === 'backend');
    const vbmetaUsable = state.vbmetaUsable ?? (appRunMode === 'webusb' ? webusbFastbootReady : backendFastbootUsable);
    const vbmetaSelected = !!document.getElementById('vbmetaSelect')?.value;
    const setText = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
    setText('rebootHint', anyUsable ? '可用：已检测到 ADB 或 Fastboot 设备。' : '按钮不可用：请先检测 ADB/Fastboot 设备。');
    const modeName = appRunMode === 'webusb' ? 'WebUSB Fastboot' : '后端 Fastboot';
    let vb = `可用：已选择 vbmeta 镜像，将通过 ${modeName} 执行关闭校验。`;
    if (!vbmetaUsable) vb = appRunMode === 'webusb'
        ? '按钮不可用：请先在 WebUSB 模式检测并连接 Fastboot/Bootloader 设备。'
        : '按钮不可用：请先检测到 Fastboot/Bootloader 设备。';
    else if (!vbmetaSelected) vb = '按钮不可用：请先选择 vbmeta 镜像。';
    setText('vbmetaHint', vb);
    setText('slotHint', fastbootUsable ? '可用：已检测到 Fastboot 设备。切槽前请确认目标槽位可启动。' : '按钮不可用：需要 Fastboot 设备在线。');
    setText('wipeHint', fastbootUsable ? '可用但高危：执行后数据无法恢复。' : '按钮不可用：需要 Fastboot 设备在线。');
    setText('blHint', fastbootUsable ? '可用但高危：解锁/上锁可能清空数据。' : '按钮不可用：需要 Fastboot 设备在线。');
}