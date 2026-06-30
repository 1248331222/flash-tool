// flash_tool/static/js/webusb.js
function validateWebUsbScriptImages() {
    if (stepList.length === 0) return {ok: true, missing: []};
    const missing = [];
    for (const step of stepList) {
        if (step.type !== 'flash' || !step.fileName) continue;
        const cached = romImageCache[step.fileName];
        if (!cached || !cached.bytes || cached.bytes.length === 0) {
            missing.push(step.fileName);
        }
    }
    return {ok: missing.length === 0, missing};
}

function fastbootArgsToWebUsbCommand(args) {
    if (!Array.isArray(args) || args.length === 0) return null;
    const cmd = String(args[0] || '').toLowerCase();
    if (cmd === 'flash') {
        return {command: 'flash', partition: args[1], payload: args[2] || ''};
    }
    if (cmd === 'erase') {
        return {command: 'erase', partition: args[1]};
    }
    if (cmd === 'reboot') {
        return {command: 'reboot', target: args[1] || 'system'};
    }
    if (cmd === 'set_active') {
        return {command: 'set_active', slot: args[1]};
    }
    if (cmd === 'getvar') {
        return {command: 'getvar', variable: args[1]};
    }
    if (cmd === 'oem') {
        return {command: 'oem', sub: args.slice(1).join(' ')};
    }
    if (cmd === 'flashing') {
        return {command: 'flashing', sub: args.slice(1).join(' ')};
    }
    return null;
}

function showWebUsbSelectedDevice(device) {
    const card = document.getElementById('webusbDeviceCard');
    if (!card) return;
    const info = document.getElementById('webusbDeviceInfo');
    if (!device) {
        card.style.display = 'none';
        info.textContent = '';
        return;
    }
    card.style.display = 'block';
    const name = device.productName || device.serialNumber || '未知设备';
    const serial = device.serialNumber || '未知';
    info.innerHTML = `<strong>${escHtml(name)}</strong><br>序列号：${escHtml(serial)}`;
    writeLog(`已选择 WebUSB 设备：${name}（${serial}）`, 'ok');
}

async function detectWebUsbDevice() {
    if (!navigator.usb) {
        setModuleStatus('single', 'WebUSB 状态：当前浏览器不支持 WebUSB。', 'err');
        writeLog('当前浏览器不支持 WebUSB', 'err');
        return false;
    }
    setModuleStatus('single', 'WebUSB 状态：正在请求设备…', 'info');
    try {
        const device = await navigator.usb.requestDevice({filters: []});
        await device.open();
        selectedUsbDevice = device;
        showWebUsbSelectedDevice(device);
        // 默认尝试 ADB 接口
        const claimed = await claimWebUsbInterface(device);
        if (!claimed) {
            // 尝试 Fastboot 接口
            const fb = await claimWebUsbFastboot(device);
            if (fb) {
                webusbFastbootReady = true;
                deviceMode = 'webusb-fastboot';
                setModuleStatus('single', 'WebUSB 状态：Fastboot 接口已就绪。', 'ok');
                writeLog('WebUSB Fastboot 设备已连接', 'ok');
                await refreshDeviceInfoAuto();
                updateBtnState();
                return true;
            }
        }
        if (claimed) {
            webusbAdbReady = true;
            deviceMode = 'webusb-adb';
            setModuleStatus('single', 'WebUSB 状态：ADB 接口已就绪。', 'ok');
            writeLog('WebUSB ADB 设备已连接', 'ok');
            updateBtnState();
            return true;
        }
        setModuleStatus('single', 'WebUSB 状态：设备已连接，但未识别到 ADB/Fastboot 接口。', 'warn');
        return false;
    } catch(e) {
        setModuleStatus('single', `WebUSB 状态：连接失败：${e.message}`, 'err');
        writeLog('WebUSB 连接失败：' + e.message, 'err');
        return false;
    }
}

async function waitForFastbootReconnect(timeoutMs = 60000) {
    const start = Date.now();
    writeLog('等待设备以 Fastboot 模式重新连接…', 'info');
    while (Date.now() - start < timeoutMs) {
        try {
            const res = await apiGet('/api/device');
            if (res.connected && res.count > 0) {
                canFastboot = true;
                deviceMode = 'fastboot';
                writeLog('Fastboot 设备已重新连接', 'ok');
                await refreshDeviceInfoAuto();
                updateBtnState();
                return true;
            }
        } catch(e) {}
        await sleep(2000);
    }
    writeLog('等待 Fastboot 重连超时', 'warn');
    return false;
}

async function recoverFastbootAfterScriptReboot(reason = '') {
    writeLog(`检测到脚本重启断联${reason ? '（' + reason + '）' : ''}，尝试恢复 Fastboot 连接…`, 'info');
    canFastboot = false;
    canAdb = false;
    deviceMode = '';
    setModuleStatus('batch', '线刷状态：设备重启中，正在等待 Fastboot 重连…', 'warn');
    showModuleProgress('batch', '等待 Fastboot 重连…');
    const ok = await waitForFastbootReconnect(120000);
    if (ok) {
        hideModuleProgress('batch');
        setModuleStatus('batch', '线刷状态：Fastboot 已重连，继续执行。', 'ok');
        return true;
    }
    hideModuleProgress('batch');
    setModuleStatus('batch', '线刷状态：Fastboot 重连超时，请重新插拔设备并点击检测。', 'err');
    return false;
}

function pauseWebUsbBatchAfterReboot(stepIndex, reason = '') {
    saveBackendReconnectCheckpoint(stepIndex, 'webusb-reboot' + (reason ? ':' + reason : ''));
    writeLog(`脚本在第 ${stepIndex + 1} 步触发重启，已暂停并保存断点。请等待设备以 Fastboot 重连后点击"恢复线刷"。`, 'warn');
    setModuleStatus('batch', `线刷状态：第 ${stepIndex + 1} 步重启，已暂停，等待重连恢复。`, 'warn');
    showModuleProgress('batch', '等待 Fastboot 重连…');
    updateBatchActionState();
}

function saveBackendReconnectCheckpoint(nextIndex, reason = '') {
    const progress = localStorage.getItem('batch_progress');
    if (progress) {
        try {
            const data = JSON.parse(progress);
            data.step_index = nextIndex;
            data.reconnect_reason = reason;
            data.saved_at = Date.now();
            localStorage.setItem('batch_progress', JSON.stringify(data));
        } catch(e) {}
    }
    localStorage.setItem('batch_waiting_reconnect', '1');
}

function clearReconnectCheckpoint() {
    localStorage.removeItem('batch_waiting_reconnect');
}

function shouldAutoResumeAfterReconnect() {
    return localStorage.getItem('batch_waiting_reconnect') === '1' && localStorage.getItem('batch_progress');
}

function isExpectedRebootDisconnect(res) {
    if (!res) return false;
    const text = String(res.error || res.message || '').toLowerCase();
    return /device not found|no devices|offline|disconnected|timeout|reset|reboot/i.test(text);
}

async function doWebUsbBatchFlash() {
    if (stepList.length === 0) {
        showToast('请先解析刷机脚本');
        return;
    }
    if (!webusbFastbootReady) {
        showToast('请先连接 WebUSB Fastboot 设备');
        return;
    }
    const validation = validateWebUsbScriptImages();
    if (!validation.ok) {
        showConfirm(
            '缺少镜像文件',
            `以下镜像未缓存，WebUSB 线刷需要全部镜像已下载：\n${validation.missing.join('\n')}\n\n请先在 ROM 管理中下载这些镜像，或在后端模式下执行线刷（后端可按需读取）。`,
            null,
            false
        );
        return;
    }
    let resumeIndex = 0;
    if (shouldAutoResumeAfterReconnect()) {
        const saved = localStorage.getItem('batch_progress');
        try {
            const data = JSON.parse(saved);
            resumeIndex = Math.max(0, Number(data.step_index || 0));
            writeLog(`从断点恢复 WebUSB 线刷，起始步骤：${resumeIndex + 1}`, 'info');
        } catch(e) {}
        clearReconnectCheckpoint();
    }
    batchRunning = true;
    batchPaused = false;
    batchCurrentIndex = resumeIndex;
    document.getElementById('batchFlashBtn').disabled = true;
    showModuleProgress('batch', `WebUSB 线刷 0/${stepList.length}`);
    try {
        for (let i = resumeIndex; i < stepList.length; i++) {
            if (batchPaused) {
                writeLog('WebUSB 线刷已暂停', 'warn');
                saveBackendReconnectCheckpoint(i, 'paused');
                break;
            }
            batchCurrentIndex = i;
            const step = stepList[i];
            updateModuleProgress('batch', Math.round(i / stepList.length * 100), `第 ${i + 1}/${stepList.length} 步：${step.raw || step.type}`);
            appendBatchOutput(`[${i + 1}/${stepList.length}] ${step.raw || step.type} ${step.part || ''} ${step.fileName || ''}`);
            try {
                if (step.type === 'flash') {
                    const cached = romImageCache[step.fileName];
                    await runWebUsbFastbootCommand({command: 'flash', partition: step.part, payload: cached.bytes});
                } else if (step.type === 'erase') {
                    await webusbEraseWithFallback(step.part);
                } else if (step.type === 'set_active') {
                    await runWebUsbFastbootCommand({command: 'set_active', slot: step.part});
                } else if (step.type === 'reboot') {
                    await runWebUsbFastbootCommand({command: 'reboot', target: step.part || 'system'});
                    if (i < stepList.length - 1) {
                        pauseWebUsbBatchAfterReboot(i, 'script-reboot');
                        return;
                    }
                } else if (step.type === 'oem') {
                    await runWebUsbFastbootCommand({command: 'oem', sub: step.part});
                }
                appendBatchOutput(`  -> 完成`, 'ok');
            } catch(e) {
                appendBatchOutput(`  -> 失败：${e.message}`, 'err');
                if (isExpectedRebootDisconnect({error: e.message})) {
                    pauseWebUsbBatchAfterReboot(i, 'disconnect:' + e.message);
                    return;
                }
                throw e;
            }
            await sleep(300);
        }
        hideModuleProgress('batch');
        setModuleStatus('batch', '线刷状态：WebUSB 线刷完成。', 'ok');
        writeLog('WebUSB 线刷全部完成', 'ok');
        showToast('WebUSB 线刷完成');
        clearReconnectCheckpoint();
    } catch(e) {
        hideModuleProgress('batch');
        setModuleStatus('batch', `线刷状态：WebUSB 线刷失败：${e.message}`, 'err');
        writeLog('WebUSB 线刷失败：' + e.message, 'err');
        showErrorCard('WebUSB 线刷失败', e.message);
    } finally {
        batchRunning = false;
        document.getElementById('batchFlashBtn').disabled = false;
        updateBatchActionState();
    }
}

function appendBatchOutput(text, level = 'info') {
    const box = document.getElementById('batchOutputArea');
    if (!box) return;
    const line = document.createElement('div');
    line.className = `batch-output-line batch-output-${level}`;
    line.textContent = text;
    box.appendChild(line);
    box.scrollTop = box.scrollHeight;
    writeLog(text, level);
}
