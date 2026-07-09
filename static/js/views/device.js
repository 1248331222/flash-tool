// flash_tool/static/js/device.js
// ============ 环境检查 ============
async function checkEnv() {
    try {
        const d = await apiGet('/api/env/check');
        envStatusBaseClass = 'env-status ok';
        envStatusBaseText = '后端服务可用';
        document.getElementById('envTip').textContent = '点击「检测设备」检测并选择设备；如手机弹出 USB 调试 / OTG / Termux:API 等授权窗口，请点击「允许」。';
        App.set('backendReady', true);
    } catch(e) {
        envStatusBaseClass = 'env-status error';
        envStatusBaseText = '❌ 无法连接后端服务';
        App.set('realtimeConnected', false);
        writeLog('后端连接失败：' + e.message, 'err');
        App.set('backendReady', false);
    }
}

// ============ 设备槽位 ============
async function loadDeviceSlot() {
    try {
        let res = null;
        if (appRunMode === 'webusb' && webusbFastbootReady && webusbFastboot) {
            const out = await webusbFastboot.command('getvar:current-slot');
            const raw = formatCommandResult(out);
            const m = raw.match(/current-slot\s*:\s*([ab])|^([ab])$/i);
            res = m ? {success: true, ab_device: true, slot: (m[1] || m[2]).toLowerCase()} : {success: true, ab_device: false, slot: ''};
        } else {
            res = await apiGet('/api/device/slot');
        }
        if (res.success && res.ab_device) {
            App.set('isAbDevice', true);
            App.set('currentSlot', res.slot);
            writeLog(`AB分区设备，当前槽位：${res.slot.toUpperCase()}`, 'ok');
        } else {
            App.set('isAbDevice', false);
            writeLog('非AB分区设备', 'tip');
        }
    } catch(e) {
        writeLog('槽位检测失败：' + e.message, 'err');
    }
}

// 注：formatPartition 已移至 utils.js（通用辅助函数）

// ============ 设备检测 ============


// ============ BL锁状态解析 ============
function formatBlStatus(value) {
    const raw = String(value || '').trim();
    const v = raw.toLowerCase();
    const m = v.match(/(?:unlocked|device unlocked)\s*[:=]\s*(yes|no|true|false|1|0)/);
    const normalized = m ? m[1] : v;
    if (['yes', 'true', '1', 'unlocked'].includes(normalized)) {
        return 'Bootloader状态：已解锁';
    }
    if (['no', 'false', '0', 'locked'].includes(normalized)) {
        return 'Bootloader状态：未解锁';
    }
    return 'Bootloader状态：未能明确判断';
}

function applyBlStatusFromText(raw) {
    const status = formatBlStatus(raw);
    App.set('blStatusText', status);
    App.set('blUnlocked', status.includes('已解锁') ? true : (status.includes('未解锁') ? false : null));
    return status;
}

async function refreshBlStatusAuto() {
    try {
        if (!(canFastboot || webusbFastbootReady)) {
            App.set('blUnlocked', null);
            App.set('blStatusText', 'Bootloader状态：未查询');
            return;
        }
        let raw = '';
        if (appRunMode === 'webusb' && webusbFastbootReady && webusbFastboot) {
            const out = await webusbFastboot.command('getvar:unlocked');
            raw = formatCommandResult(out);
        } else {
            const res = await apiGet('/api/device/bl');
            raw = res.status_text || res.analysis || JSON.stringify(res.info || {});
        }
        if (!raw || formatBlStatus(raw).includes('未能明确判断')) {
            try {
                const fallback = await (appRunMode === 'webusb' && webusbFastbootReady && webusbFastboot
                    ? webusbFastboot.command('getvar:unlocked').then(formatCommandResult)
                    : apiPost('/api/fastboot', {args: ['getvar', 'unlocked']}).then(formatCommandResult));
                if (fallback) raw = fallback;
            } catch(e) {}
        }
        const status = applyBlStatusFromText(raw);
        writeLog(`自动查询Bootloader：${status}`, status.includes('已解锁') ? 'ok' : 'tip');
    } catch(e) {
        App.set('blUnlocked', null);
        App.set('blStatusText', 'Bootloader状态：未能明确判断');
        writeLog('自动查询Bootloader失败：' + e.message, 'tip');
    }
}

async function refreshDeviceInfoAuto() {
    try {
        if (!(canFastboot || webusbFastbootReady)) {
            App.set('deviceInfo', {});
            return;
        }
        let info = {};
        if (appRunMode === 'webusb' && webusbFastbootReady && webusbFastboot) {
            const vars = ['product','product-name','variant','current-slot','serialno','is-userspace','battery-soc','battery-voltage'];
            for (const v of vars) {
                try {
                    const out = await webusbFastboot.command('getvar:' + v);
                    const raw = formatCommandResult(out);
                    const value = extractFastbootVar(raw, v);
                    if (value) info[v.replace(/-/g, '_').replace('serialno','serial')] = value;
                } catch(e) {}
            }
            if (info.product) info.product_display = info.product;
            else if (info.product_name) info.product_display = info.product_name;
        } else {
            const res = await apiGet('/api/device/info');
            info = (res && res.info) ? res.info : {};
        }
        App.set('deviceInfo', info);
        if (info.current_slot) {
            App.set('currentSlot', String(info.current_slot).replace(/^_/, '').toLowerCase());
            App.set('isAbDevice', true);
        }
    } catch(e) {
        writeLog('自动读取设备信息失败：' + e.message, 'tip');
    }
}

// ============ BL锁 ============
// ============ 刷机历史 ============
async function loadFlashHistory() {
    const listEl = document.getElementById('flashHistoryList');
    if (!listEl) return;
    listEl.innerHTML = '加载中...';
    try {
        const res = await apiGet('/api/history');
        if (!res.success || !res.history || res.history.length === 0) {
            listEl.innerHTML = '<p class="tip">暂无刷机历史记录</p>';
            return;
        }
        let html = '<table style="width:100%;font-size:12px;border-collapse:collapse;">';
        html += '<tr style="border-bottom:1px solid var(--border-color);color:var(--text-secondary);"><th style="text-align:left;padding:4px;">时间</th><th style="text-align:left;padding:4px;">设备</th><th style="text-align:left;padding:4px;">脚本</th><th style="text-align:left;padding:4px;">结果</th></tr>';
        for (const item of res.history.reverse()) {
            const statusStyle = item.success ? 'color:var(--accent-green)' : 'color:var(--danger-color)';
            const statusText = item.success ? '成功' : '失败';
            html += `<tr style="border-bottom:1px solid var(--border-color);"><td style="padding:4px;">${escHtml(item.time)}</td><td style="padding:4px;">${escHtml(item.device || '-')}</td><td style="padding:4px;">${escHtml(item.script || '-')}</td><td style="padding:4px;${statusStyle}">${statusText}${item.error ? ' ' + escHtml(item.error) : ''}</td></tr>`;
        }
        html += '</table>';
        listEl.innerHTML = html;
    } catch(e) {
        listEl.innerHTML = '<p class="tip" style="color:var(--danger-color)">加载失败：' + e.message + '</p>';
    }
}

// ============ 模块初始化 ============
Modules.register('device', ['ui'], function initDeviceModule() {
    $('loadHistoryBtn').onclick = loadFlashHistory;

    $('checkDeviceBtn').onclick = async () => {
        $('checkDeviceBtn').disabled = true;
        try {
            if (appRunMode === 'webusb') {
                await detectWebUsbDevice();
                $('checkDeviceBtn').disabled = false;
                return;
            }
            const d = await apiGet('/api/device/state');
            App.set('deviceMode', d.mode || 'none');
            App.set('canAdb', !!d.can_adb);
            App.set('canFastboot', !!d.can_fastboot);
            const adbDetected = !!(d.adb && d.adb.connected);
            const fastbootDetected = !!(d.fastboot && d.fastboot.connected);
            App.set('deviceConnected', !!(d.can_adb || d.can_fastboot));
            const sel = $('deviceSelect');
            sel.innerHTML = '<option value="">自动选择设备</option>';
            if (adbDetected || fastbootDetected) {
                const devices = [];
                (d.fastboot.devices || []).forEach((dev, idx) => devices.push({...dev, mode: 'fastboot', label: `Fastboot设备${idx + 1}`}));
                (d.adb.devices || []).forEach((dev, idx) => devices.push({...dev, mode: 'adb', label: `ADB设备${idx + 1}`}));
                devices.forEach((dev) => {
                    const opt = document.createElement('option');
                    opt.value = dev.serial;
                    opt.dataset.mode = dev.mode;
                    opt.textContent = `${dev.label}${dev.state ? ' · ' + dev.state : ''}`;
                    sel.appendChild(opt);
                });
                if (d.selected) sel.value = d.selected;
                const total = (d.fastboot.count || 0) + (d.adb.count || 0);
                let statusText = '';
                let statusType = 'ok';
                if (canFastboot) {
                    statusText = `设备状态：Fastboot/Bootloader，已检测到 ${d.fastboot.count} 个 Fastboot 设备。当前可用：线刷、单分区刷写、Bootloader/槽位/fastboot命令。`;
                } else if (canAdb) {
                    statusText = `设备状态：ADB ${d.state}，已检测到 ${d.adb.count} 个 ADB 设备。当前可用：ADB命令、重启到Bootloader/Recovery、Sideload相关命令。`;
                } else {
                    const states = (d.adb.devices || []).map(x => x.state).join('、') || '未知';
                    statusText = `设备状态：已发现 ${total} 个设备，但当前不可操作。ADB状态：${states}。如果是 unauthorized，请看被刷手机弹窗并允许 USB 调试；如果是 offline，请重新插拔或重启 ADB。`;
                    statusType = 'warn';
                }
                setModuleStatus('envDevice', statusText, statusType);
                writeLog(`检测到 ${total} 台设备（Fastboot ${d.fastboot.count || 0} / ADB ${d.adb.count || 0}）`, statusType === 'ok' ? 'ok' : 'tip');
                if (canFastboot) {
                    await loadDeviceSlot();
                    await refreshBlStatusAuto();
                    await refreshDeviceInfoAuto();
                    if (shouldAutoResumeAfterReconnect()) {
                        if ($('batchFlashBtn').disabled) {
                            writeLog('检测到重启后设备已重连，当前线刷任务会自动继续。', 'ok');
                        } else {
                            writeLog('检测到重启后设备已重连，稍等1.5秒后自动从断点继续线刷。', 'ok');
                            setTimeout(() => $('resumeFlashBtn').click(), 1500);
                        }
                    }
                }
            } else {
                let usbTip = '';
                const adbErr = d.adb && d.adb.error ? d.adb.error : '';
                const fbErr = d.fastboot && d.fastboot.error ? d.fastboot.error : '';
                if (adbErr && (adbErr.includes('No such file') || adbErr.includes('not found') || adbErr.includes('Permission denied'))) {
                    writeLog(`ADB 二进制异常：${adbErr}`, 'err');
                    usbTip += 'ADB 工具不可用（' + adbErr.substring(0, 60) + '）。请在 Termux 执行 pkg install android-tools 或重新部署工具。';
                }
                if (fbErr && (fbErr.includes('No such file') || fbErr.includes('not found') || fbErr.includes('Permission denied'))) {
                    writeLog(`Fastboot 二进制异常：${fbErr}`, 'err');
                    usbTip += 'Fastboot 工具不可用（' + fbErr.substring(0, 60) + '）。请重新部署工具。';
                }
                try {
                    const usb = await apiGet('/api/usb/list');
                    if (usb.success && usb.count > 0) {
                        if (!usbTip) usbTip = `已看到 ${usb.count} 个 USB 设备，但它没有出现在 ADB/Fastboot 中。请确认手机模式：开机用 ADB 需打开 USB 调试并授权；刷机用 Fastboot 需进入 Bootloader/Fastboot。`;
                    } else {
                        if (!usbTip) usbTip = 'Termux 未看到 USB 设备，请检查 OTG 线、接口方向、被刷手机是否通电。';
                    }
                } catch(e) {
                    if (!usbTip) usbTip = '无法读取 USB 设备列表，请确认 Termux:API APP 与 termux-api 包已安装。';
                }
                setModuleStatus('envDevice', `设备状态：未检测到 ADB/Fastboot 设备。${usbTip}`, 'err');
                writeLog('没检测到 ADB/Fastboot 设备' + (adbErr ? ' (ADB: ' + adbErr.substring(0, 50) + ')' : ''), 'err');
            }
        } catch(e) { writeLog('检测失败：' + e.message, 'err'); }
        $('checkDeviceBtn').disabled = false;
    };

    $('querySlotBtn').onclick = async () => {
        setModuleStatus('envDevice', '设备状态：正在查询 AB 槽位。', 'info');
        await loadDeviceSlot();
    };

    $('deviceSelect').onchange = async () => {
        const sel = $('deviceSelect');
        const serial = sel.value;
        const selectedOption = sel.selectedOptions[0];
        const mode = selectedOption ? (selectedOption.dataset.mode || (canFastboot ? 'fastboot' : 'adb')) : (canFastboot ? 'fastboot' : 'adb');
        try {
            const res = await apiPost('/api/device/select', {serial, mode});
            if (res.success) {
                setModuleStatus('envDevice', serial ? `设备状态：已选择设备 ${serial}` : '设备状态：已切换为自动选择设备。', 'ok');
                writeLog(res.msg, 'ok');
                if (serial && mode === 'fastboot') await loadDeviceSlot();
            } else {
                setModuleStatus('envDevice', `设备状态：选择设备失败：${res.error || '未知错误'}`, 'err');
            }
        } catch(e) {
            setModuleStatus('envDevice', `设备状态：选择设备异常：${e.message}`, 'err');
        }
    };

    $('checkBlBtn').onclick = async () => {
        setModuleStatus('toolbox', '工具箱状态：正在查询 Bootloader 锁状态。', 'info');
        showModuleProgress('toolbox', '查询 Bootloader');
        if (appRunMode === 'webusb' && webusbFastbootReady) {
            try {
                const out = await webusbFastboot.command('getvar:unlocked');
                updateModuleProgress('toolbox', 100, '查询完成');
                const raw = formatCommandResult(out);
                const statusText = applyBlStatusFromText(raw);
                setModuleStatus('toolbox', `工具箱状态：WebUSB Bootloader锁状态查询完成。${statusText}。`, 'ok');
                writeLog(`WebUSB Bootloader锁查询结果：${statusText}（原始值：${raw || '空'}）`, 'ok');
            } catch(e) {
                App.set('blUnlocked', null);
                App.set('blStatusText', 'Bootloader状态：未能明确判断');
                setModuleStatus('toolbox', '工具箱状态：WebUSB Bootloader查询失败：' + e.message, 'err');
            }
            return;
        }
        const res = await apiGet('/api/device/bl');
        updateModuleProgress('toolbox', 100, '查询完成');
        if (res.success) {
            const infoText = JSON.stringify(res.info || {});
            const statusText = applyBlStatusFromText(res.status_text || res.analysis || infoText);
            setModuleStatus('toolbox', `工具箱状态：Bootloader 锁状态查询完成。${statusText}`, 'ok');
            writeLog(`Bootloader锁查询结果：${statusText} 原始信息：${infoText}`, 'ok');
            if (res.analysis) writeLog('分析：' + res.analysis, 'tip');
        } else {
            App.set('blUnlocked', null);
            App.set('blStatusText', 'Bootloader状态：未能明确判断');
            setModuleStatus('toolbox', '工具箱状态：Bootloader 查询失败，设备可能不支持这些 fastboot 查询命令。', 'err');
            writeLog('Bootloader查询失败：设备不支持 oem device-info 或通用查询命令', 'err');
        }
    };

    $('unlockBlBtn').onclick = () => {
        showConfirm('解锁确认', '解锁Bootloader会清空设备所有数据，确认继续？', async () => {
            setModuleStatus('toolbox', '工具箱状态：正在发送解锁 Bootloader 指令。', 'warn');
            showModuleProgress('toolbox', '解锁 Bootloader');
            const res = (appRunMode === 'webusb' && webusbFastbootReady)
                ? await webusbFastboot.command('oem unlock').then(() => ({success: true}))
                : await apiPost('/api/fastboot', {args: ['oem', 'unlock']});
            updateModuleProgress('toolbox', 100, '命令完成');
            setModuleStatus('toolbox', res.success ? '工具箱状态：已发送解锁 Bootloader 指令。' : `工具箱状态：解锁 Bootloader 失败：${res.error}`, res.success ? 'ok' : 'err');
            res.success ? writeLog('解锁指令已发送', 'ok') : writeLog(res.error, 'err');
            if (res.success) {
                App.set('blUnlocked', null);
                App.set('blStatusText', 'Bootloader状态：未查询');
            }
        });
    };

    $('lockBlBtn').onclick = () => {
        showConfirm('上锁确认', '上锁Bootloader会清空所有数据，请确保已刷入官方系统，确认继续？', async () => {
            setModuleStatus('toolbox', '工具箱状态：正在发送上锁 Bootloader 指令。', 'warn');
            showModuleProgress('toolbox', '上锁 Bootloader');
            const res = (appRunMode === 'webusb' && webusbFastbootReady)
                ? await webusbFastboot.command('oem lock').then(() => ({success: true}))
                : await apiPost('/api/fastboot', {args: ['oem', 'lock']});
            updateModuleProgress('toolbox', 100, '命令完成');
            setModuleStatus('toolbox', res.success ? '工具箱状态：已发送上锁 Bootloader 指令。' : `工具箱状态：上锁 Bootloader 失败：${res.error}`, res.success ? 'ok' : 'err');
            res.success ? writeLog('上锁指令已发送', 'ok') : writeLog(res.error, 'err');
            if (res.success) {
                App.set('blUnlocked', null);
                App.set('blStatusText', 'Bootloader状态：未查询');
            }
        });
    };

    console.log('[device] 设备模块已初始化');
    return true;
});

// ============ 错误诊断卡片 ============
function showErrorCard(error, diagnosis) {
    const target = getLogBoxForView();
    const card = document.createElement('div');
    card.className = 'error-card';
    card.innerHTML = `
        <div class="error-title">❌ ${escHtml(error)}</div>
        <div class="diagnosis-box">
            <strong>💡 解决建议：</strong>
            <p>${escHtml(diagnosis) || '暂无建议'}</p>
        </div>
    `;
    target.appendChild(card);
    target.scrollTop = target.scrollHeight;
}

async function diagnoseFastbootError(errorText) {
    const e = String(errorText || '').toLowerCase();
    if (!e) return '';
    // 优先调用后端诊断 API（支持 18 种规则）
    try {
        const res = await apiPost('/api/diagnose', { error: String(errorText || '') });
        if (res.success && res.diagnosis) {
            return res.diagnosis;
        }
    } catch(apiErr) {
        // API 调用失败，回退到本地匹配
    }
    // 后备：本地简单匹配（5 种常见模式）
    if (e.includes('partition flashing is not allowed') || e.includes('not allowed in locked state')) {
        return '可能原因：Bootloader 未解锁或当前分区禁止刷写。建议先查询 Bootloader 状态，确认已解锁后再刷写。';
    }
    if (e.includes('no such partition') || e.includes('unknown partition')) {
        return '可能原因：分区名不适用于当前机型。建议确认刷机包与设备型号匹配，或检查脚本中的分区名。';
    }
    if (e.includes('sparse') || e.includes('size too large') || e.includes('overflow')) {
        return '可能原因：镜像过大或分区表不匹配。建议确认线刷包是否匹配当前机型。';
    }
    if (e.includes('unknown command')) {
        return '可能原因：当前设备或 Fastboot 版本不支持该命令。建议换用通用 getvar/flashing 命令或切换连接模式。';
    }
    if (e.includes('no devices') || e.includes('device not found') || e.includes('timeout')) {
        return '可能原因：设备断开或未处于 Fastboot/ADB 状态。建议重新检测设备，必要时重新插拔 USB。';
    }
    return '';
}

function showFlashReport(success, detail = '') {
    const done = stepList.length;
    const mode = appRunMode === 'webusb' ? 'WebUSB Fastboot' : '后端 Fastboot';
    const slot = currentSlot ? currentSlot.toUpperCase() : '未知';
    const title = success ? '线刷报告：成功' : '线刷报告：失败/中断';
    const report = `${title}\n时间：${new Date().toLocaleString()}\n模式：${mode}\nBootloader：${blStatusText}\n槽位：${slot}\n步骤：${done}\n${detail || ''}`;
    const card = document.getElementById('flashReportCard');
    if (card) {
        const product = getDeviceProduct();
        const script = document.getElementById('batSelect') ? (document.getElementById('batSelect').value || '未选择') : '未知';
        card.className = `report-card ${success ? 'ok' : 'err'}`;
        card.style.display = 'block';
        card.innerHTML = `
            <h4>${title}</h4>
            <div class="report-grid">
                <div class="report-metric"><span>结果</span>${success ? '成功' : '失败/中断'}</div>
                <div class="report-metric"><span>步骤</span>${done}</div>
                <div class="report-metric"><span>模式</span>${mode}</div>
                <div class="report-metric"><span>设备代号</span>${product}</div>
                <div class="report-metric"><span>槽位</span>${slot}</div>
                <div class="report-metric"><span>Bootloader</span>${blStatusText.replace('Bootloader状态：','')}</div>
            </div>
            <div class="report-detail">脚本：${escHtml(script)}\n时间：${new Date().toLocaleString()}\n${escHtml(detail) || ''}</div>
        `;
    }
    writeLog(report, success ? 'ok' : 'err');
}
