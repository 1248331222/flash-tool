// flash_tool/static/js/flash.js
// ============ 线刷 ============
document.getElementById('batchFlashBtn').onclick = async () => {
    if (appRunMode === 'webusb') {
        setModuleStatus('batch', '线刷状态：WebUSB模式已禁用线刷，避免大镜像占满内存导致主设备卡死。请切换到后端模式线刷。', 'err');
        writeLog('WebUSB模式已禁用线刷，请切换到后端模式执行完整线刷。', 'err');
        showErrorCard('WebUSB线刷已禁用', 'WebUSB刷写大文件会把镜像读入浏览器内存，容易导致主设备爆内存卡死。完整线刷请使用后端模式；WebUSB仅建议用于命令和单分区小镜像刷写。');
        return;
    }
    
    // v3.0.0: 复杂脚本 / 原生 .sh 模式 - 直接执行（无步骤管理）
    if (window._isComplexScript || window._isNativeSh) {
        if (!window._shContent) {
            const msg = window._isNativeSh ? '原生 .sh 脚本内容未加载' : '请先输入并确认自定义 .sh 脚本';
            setModuleStatus('batch', '线刷状态：' + msg + '。', 'err');
            writeLog(msg, 'err');
            return;
        }
        const selectedRomProject = getSelectedRomProject();
        if (!selectedRomProject) {
            setModuleStatus('batch', '线刷状态：请先选择已解压线刷项目。', 'err');
            writeLog('请先选择已解压线刷项目', 'err');
            return;
        }
        if (blUnlocked === false) {
            setModuleStatus('batch', '线刷状态：Bootloader 未解锁，已阻止线刷。', 'err');
            writeLog('Bootloader 未解锁，已阻止线刷', 'err');
            showErrorCard('Bootloader 未解锁', '大多数分区在线刷前必须先解锁 Bootloader。');
            return;
        }
        
        const confirmTitle = window._isNativeSh ? '执行原生 .sh 脚本确认' : '执行自定义脚本确认';
        const confirmMsg = window._isNativeSh 
            ? '确认执行原生 .sh 脚本？\n\n该脚本将直接在 Termux 中以 bash 执行。\n执行过程中请勿断开USB、请勿关闭浏览器。'
            : '确认执行自定义 .sh 脚本？\n\n该脚本将直接在 Termux 中以 bash 执行。\n执行过程中请勿断开USB、请勿关闭浏览器。\n\n脚本路径：' + (window._customScriptPath || '未知');
        
        showConfirm(confirmTitle, confirmMsg,
            async () => {
                const execLabel = window._isNativeSh ? '原生 .sh 脚本' : '自定义 .sh 脚本';
                setModuleStatus('batch', '线刷状态：正在执行' + execLabel + '...', 'warn');
                showModuleProgress('batch', '执行' + execLabel);
                requestWakeLock();
                writeLog('开始执行' + execLabel, 'warn');
                document.getElementById('batchFlashBtn').disabled = true;
                try {
                    const d = await apiPost('/api/batch-task/direct_execute', {
                        sh_content: window._shContent,
                        rom_name: selectedRomProject
                    });
                    if (d.success) {
                        writeLog(execLabel + '已开始执行，任务ID: ' + d.task_id, 'ok');
                        setModuleStatus('batch', '线刷状态：' + execLabel + '执行中...', 'info');
                        pollDirectExecuteTask(d.task_id);
                    } else {
                        writeLog('执行失败：' + (d.error || '未知错误'), 'err');
                        setModuleStatus('batch', '线刷状态：执行失败', 'err');
                        document.getElementById('batchFlashBtn').disabled = false;
                    }
                } catch(e) {
                    writeLog('执行出错：' + e.message, 'err');
                    setModuleStatus('batch', '线刷状态：执行出错', 'err');
                    document.getElementById('batchFlashBtn').disabled = false;
                }
            }
        );
        return;
    }
    
    // 简单脚本模式：原有步骤管理流程
    if (stepList.length === 0) {
        setModuleStatus('batch', '线刷状态：请先解析刷机脚本。', 'err');
        writeLog('请先解析刷机脚本', 'err');
        return;
    }
    const selectedRomProject = getSelectedRomProject();
    if (appRunMode !== 'webusb' && !selectedRomProject) {
        setModuleStatus('batch', '线刷状态：请先选择已解压线刷项目。', 'err');
        writeLog('请先选择已解压线刷项目', 'err');
        return;
    }
    if (blUnlocked === false) {
        setModuleStatus('batch', '线刷状态：Bootloader 未解锁，已阻止线刷。请先解锁 Bootloader 后再刷写。', 'err');
        writeLog('Bootloader 未解锁，已阻止线刷', 'err');
        showErrorCard('Bootloader 未解锁', '大多数分区在线刷前必须先解锁 Bootloader。请到工具页执行"查询锁状态/解锁Bootloader"，确认已解锁后再线刷。');
        return;
    }
    
    let startIndex = pendingResumeIndex || 0;
    const saved = localStorage.getItem('batch_progress');
    if (saved) {
        try {
            const data = JSON.parse(saved);
            if ((appRunMode === 'webusb' || data.rom_name === selectedRomProject) && data.steps.length === stepList.length) {
                startIndex = pendingResumeIndex || data.step_index;
            }
        } catch(e) {}
    }
    
    const counts = stepList.reduce((acc, s) => (acc[s.type] = (acc[s.type] || 0) + 1, acc), {});
    const risks = analyzeScriptRisks();
    const product = getDeviceProduct();
    const riskText = `高危分区：${risks.highRisk.length}${risks.highRisk.length ? '（' + risks.highRisk.slice(0, 8).join('、') + '）' : ''}\n清空数据：${risks.wipesData ? '是' : '否'}\n上锁Bootloader：${risks.locksBl ? '是' : '否'}\n设备代号：${product}`;
    const confirmText = startIndex > 0
        ? `从第 ${startIndex+1} 步开始刷，中途请勿断开，确认继续？\n\n${riskText}`
        : `确认开始线刷？\n\n模式：${appRunMode === 'webusb' ? 'WebUSB Fastboot' : '后端 Fastboot'}\n步骤：${stepList.length} 个\n刷写：${counts.flash || 0} 个，擦除：${counts.erase || 0} 个，重启：${counts.reboot || 0} 个\n${riskText}\n\n刷写过程中请勿断开USB、请勿关闭浏览器。`;
    
    showConfirm('线刷确认', confirmText, async () => {
        // v3.0.0: 复杂脚本 / 原生 .sh - 直接执行
        if ((window._isComplexScript || window._isNativeSh) && window._shContent) {
            const execLabel = window._isNativeSh ? '原生 .sh 脚本' : '自定义 .sh 脚本';
            setModuleStatus('batch', '线刷状态：正在执行' + execLabel + '...', 'warn');
            showModuleProgress('batch', '执行' + execLabel);
            requestWakeLock();
            writeLog('开始执行' + execLabel, 'warn');
            document.getElementById('batchFlashBtn').disabled = true;
            try {
                const d = await apiPost('/api/batch-task/direct_execute', {
                    sh_content: window._shContent,
                    rom_name: selectedRomProject
                });
                if (d.success) {
                    writeLog(execLabel + '已开始执行，任务ID: ' + d.task_id, 'ok');
                    setModuleStatus('batch', '线刷状态：' + execLabel + '执行中...', 'info');
                    pollDirectExecuteTask(d.task_id);
                } else {
                    writeLog('执行失败：' + (d.error || '未知错误'), 'err');
                    setModuleStatus('batch', '线刷状态：执行失败', 'err');
                    document.getElementById('batchFlashBtn').disabled = false;
                }
            } catch(e) {
                writeLog('执行出错：' + e.message, 'err');
                setModuleStatus('batch', '线刷状态：执行出错', 'err');
                document.getElementById('batchFlashBtn').disabled = false;
            }
            return;
        }

        const activeRomProject = selectedRomProject;
        try {
            await startBackendBatchTask(startIndex, activeRomProject);
        } catch(e) {
            hideProgress();
            hideModuleProgress('batch');
            releaseWakeLock();
            document.getElementById('batchFlashBtn').disabled = false;
            setModuleStatus('batch', `线刷状态：后端任务异常：${e.message}`, 'err');
            writeLog(`后端线刷任务异常：${e.message}`, 'err');
            const diagnosis = await diagnoseFastbootError(e.message);
            if (diagnosis) showErrorCard(e.message, diagnosis);
            showFlashReport(false, `后端线刷任务异常：${e.message}`);
        }
        return;
    }, false);
};

// ============ 补充函数 ============
function updateDeviceInfoSummary() {
    const el = document.getElementById('deviceInfoSummary');
    if (!el) return;
    const fastbootReady = canFastboot || webusbFastbootReady;
    if (!fastbootReady) {
        el.innerHTML = '<span class="muted">未连接 Fastboot 设备</span>';
        return;
    }
    const product = getDeviceProduct();
    const slot = currentSlot ? currentSlot.toUpperCase() : '未知';
    const userspace = String(deviceInfo.is_userspace || deviceInfo['is-userspace'] || '').trim().toLowerCase();
    const mode = userspace === 'yes' || userspace === 'true' || userspace === '1' ? 'Fastbootd' : getFastbootModeLabel();
    const battery = normalizeBatterySoc(deviceInfo.battery_soc || deviceInfo.battery);
    const voltage = normalizeVoltage(deviceInfo.battery_voltage);
    const bl = blStatusText.replace('Bootloader状态：', '') || '未查询';
    el.innerHTML = `
        <div class="info-grid">
            <div><span class="label">设备代号</span><span class="value">${escHtml(product)}</span></div>
            <div><span class="label">当前模式</span><span class="value">${escHtml(mode)}</span></div>
            <div><span class="label">当前槽位</span><span class="value">${slot}</span></div>
            <div><span class="label">电池</span><span class="value">${battery} / ${voltage}</span></div>
            <div><span class="label">Bootloader</span><span class="value">${escHtml(bl)}</span></div>
            <div><span class="label">序列号</span><span class="value">${escHtml(cleanFastbootVarValue(deviceInfo.serial) || '未知')}</span></div>
        </div>`;
}

async function runCustomFastbootCommand() {
    const tool = document.getElementById('commandTool').value || 'fastboot';
    let rawCmd = document.getElementById('customFastbootCmd').value || '';
    if (!rawCmd.trim()) {
        setModuleStatus('command', '命令状态：请输入要执行的命令。', 'warn');
        return;
    }
    const args = parseFastbootArgs(rawCmd);
    setModuleStatus('command', `命令状态：正在执行 ${tool} ${rawCmd}…`, 'info');
    showModuleProgress('command', `执行 ${tool} ${args.join(' ')}`);
    try {
        let resultText = '';
        if (appRunMode === 'webusb' && webusbFastbootReady) {
            const cmdObj = fastbootArgsToWebUsbCommand(args);
            if (cmdObj) {
                resultText = await runWebUsbFastbootCommand(cmdObj);
            } else {
                throw new Error('WebUSB 模式暂不支持该命令');
            }
        } else {
            const res = await apiPost('/api/fastboot', {args});
            if (!res.success) throw new Error(res.error || '命令执行失败');
            resultText = res.output || res.result || '';
            if (res.device_info) {
                Object.assign(deviceInfo, res.device_info);
                updateDeviceInfoSummary();
            }
        }
        const localized = localizeFastbootResult(tool, args, resultText);
        writeLog(`命令返回：${localized}`, 'ok');
        setModuleStatus('command', '命令状态：执行完成。', 'ok');
        document.getElementById('customFastbootResult').textContent = localized;
    } catch(e) {
        const msg = await diagnoseFastbootError(e.message);
        writeLog(`命令失败：${msg}`, 'err');
        setModuleStatus('command', `命令状态：${msg}`, 'err');
        document.getElementById('customFastbootResult').textContent = msg;
    } finally {
        hideModuleProgress('command');
    }
}

async function pollDirectExecuteTask(taskId) {
    if (!taskId) return;
    const poll = async () => {
        try {
            const res = await apiGet(`/api/batch-task/status/${taskId}`);
            const t = res.task;
            if (!t) { setTimeout(poll, 1500); return; }
            if (t.status === 'completed' || t.status === 'failed') {
                hideModuleProgress('batch');
                if (t.status === 'completed') {
                    appendBatchOutput('线刷任务完成', 'ok');
                    setModuleStatus('batch', '线刷状态：后端线刷完成。', 'ok');
                    writeLog('后端线刷任务完成', 'ok');
                    showToast('线刷完成');
                    clearReconnectCheckpoint();
                } else {
                    appendBatchOutput(`线刷任务失败：${t.error || '未知错误'}`, 'err');
                    setModuleStatus('batch', `线刷状态：后端线刷失败：${t.error || '未知错误'}`, 'err');
                    writeLog('后端线刷任务失败：' + (t.error || '未知错误'), 'err');
                    showErrorCard('线刷失败', t.error || '未知错误');
                }
                batchRunning = false;
                document.getElementById('batchFlashBtn').disabled = false;
                updateBatchActionState();
                return;
            }
            if (t.progress != null) {
                updateModuleProgress('batch', t.progress, t.current_step || '');
            }
            if (t.output) appendBatchOutput(t.output, 'info');
            if (t.phase === 'reconnect') {
                setModuleStatus('batch', '线刷状态：设备重启中，等待 Fastboot 重连…', 'warn');
            }
            setTimeout(poll, 1500);
        } catch(e) {
            writeLog('轮询线刷任务失败：' + e.message, 'err');
            setTimeout(poll, 3000);
        }
    };
    poll();
}

async function startBackendBatchTask(startIndex, romName) {
    if (stepList.length === 0) {
        showToast('请先解析刷机脚本');
        return;
    }
    if (!backendReady || !canFastboot) {
        showToast('请先检测 Fastboot 设备');
        return;
    }
    batchRunning = true;
    document.getElementById('batchFlashBtn').disabled = true;
    showModuleProgress('batch', `后端线刷 0/${stepList.length}`);
    try {
        const res = await apiPost('/api/batch-task/start', {
            steps: stepList,
            start_index: startIndex || 0,
            source: 'rom',
            rom_name: romName || activeRomProject || ''
        });
        if (!res.success || !res.task_id) {
            throw new Error(res.error || '无法启动后端线刷任务');
        }
        clearReconnectCheckpoint();
        batchTaskId = res.task_id;
        writeLog(`后端线刷任务已启动，任务ID：${res.task_id}`, 'ok');
        pollBackendBatchTask(res.task_id);
    } catch(e) {
        hideModuleProgress('batch');
        setModuleStatus('batch', `线刷状态：启动后端线刷失败：${e.message}`, 'err');
        writeLog('启动后端线刷失败：' + e.message, 'err');
        batchRunning = false;
        document.getElementById('batchFlashBtn').disabled = false;
        updateBatchActionState();
    }
}

function pollBackendBatchTask(taskId) {
    if (!taskId) return;
    const poll = async () => {
        try {
            const res = await apiGet(`/api/batch-task/status/${taskId}`);
            const t = res.task;
            if (!t) { setTimeout(poll, 1500); return; }
            if (t.status === 'completed' || t.status === 'failed') {
                hideModuleProgress('batch');
                if (t.status === 'completed') {
                    appendBatchOutput('后端线刷任务完成', 'ok');
                    setModuleStatus('batch', '线刷状态：后端线刷完成。', 'ok');
                    writeLog('后端线刷任务完成', 'ok');
                    showToast('线刷完成');
                    clearReconnectCheckpoint();
                    showFlashReport();
                } else {
                    appendBatchOutput(`后端线刷失败：${t.error || '未知错误'}`, 'err');
                    setModuleStatus('batch', `线刷状态：后端线刷失败：${t.error || '未知错误'}`, 'err');
                    writeLog('后端线刷任务失败：' + (t.error || '未知错误'), 'err');
                    showErrorCard('线刷失败', t.error || '未知错误');
                }
                batchRunning = false;
                batchTaskId = null;
                document.getElementById('batchFlashBtn').disabled = false;
                updateBatchActionState();
                return;
            }
            if (t.progress != null) {
                updateModuleProgress('batch', t.progress, t.current_step || '');
            }
            if (t.output) appendBatchOutput(t.output, 'info');
            if (t.phase === 'reconnect') {
                setModuleStatus('batch', '线刷状态：设备重启中，等待 Fastboot 重连…', 'warn');
                saveBackendReconnectCheckpoint(t.step_index || 0, 'backend-reboot');
            }
            setTimeout(poll, 1500);
        } catch(e) {
            writeLog('轮询后端线刷任务失败：' + e.message, 'err');
            setTimeout(poll, 3000);
        }
    };
    poll();
}

async function restoreBackendBatchTaskIfRunning() {
    try {
        const res = await apiGet('/api/batch-task/latest');
        if (res.task && res.task.status === 'running') {
            const taskId = res.task.id;
            batchRunning = true;
            document.getElementById('batchFlashBtn').disabled = true;
            writeLog('检测到运行中的线刷任务，正在恢复轮询...', 'info');
            pollBackendBatchTask(taskId);
        }
    } catch(e) {
        // 静默失败
    }
}
