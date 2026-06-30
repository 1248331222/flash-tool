// flash_tool/static/js/bat.js
// ============ BAT 脚本 ============
async function refreshBatList() {
    const rn = getSelectedRomProject();
    if (!rn) { writeLog('请先选择已解压线刷项目', 'err'); return; }
    
    document.getElementById('batSelect').innerHTML = '<option value="">加载中...</option>';
    try {
        const d = await apiGet(`/api/rom/bats?rom_name=${encodeURIComponent(rn)}`);
        if (d.success) {
            fillSelect(document.getElementById('batSelect'), d.files, '选择刷机脚本');
            document.getElementById('importBatBtn').disabled = !document.getElementById('batSelect').value;
        } else {
            writeLog(d.error, 'err');
            document.getElementById('batSelect').innerHTML = '<option value="">加载失败</option>';
        }
    } catch(e) { writeLog('获取脚本失败', 'err'); }
}

document.getElementById('refreshBatBtn').onclick = refreshBatList;

document.getElementById('romProjectSelect').onchange = () => {
    stepList = [];
    renderSteps();
    document.getElementById('batSelect').innerHTML = '<option value="">选择刷机脚本</option>';
    document.getElementById('importBatBtn').disabled = true;
    document.getElementById('simulateBtn').disabled = true;
    if (document.getElementById('romProjectSelect').value) refreshBatList();
};

document.getElementById('batSelect').onchange = () => {
    document.getElementById('importBatBtn').disabled = !document.getElementById('batSelect').value;
};

document.getElementById('importBatBtn').onclick = async () => {
    const rn = getSelectedRomProject();
    const bp = document.getElementById('batSelect').value;
    if (!rn || !bp) return;
    
    document.getElementById('importBatBtn').disabled = true;
    writeLog(`解析脚本：${bp}`);
    
    try {
        const d = await apiPost('/api/rom/import_bat', {rom_name: rn, bat_path: bp});
        if (d.success) {
            stepList = d.steps || [];
            const scriptType = d.script_type || 'bat';
            const isComplex = d.is_complex || false;
            const isNativeSh = d.is_native_sh || false;
            window._scriptType = scriptType;
            window._isComplexScript = isComplex;
            window._isNativeSh = isNativeSh;
            window._shContent = '';
            window._batSourceContent = d.content || '';
            
            // 重置脚本处理区域
            document.getElementById('scriptProcessArea').style.display = '';
            document.getElementById('complexScriptBanner').style.display = 'none';
            document.getElementById('batSourceDetails').style.display = 'none';
            document.getElementById('shNativePreviewArea').style.display = 'none';
            document.getElementById('customScriptArea').style.display = 'none';
            document.getElementById('stepList').style.display = '';
            document.getElementById('toggleStepsBtn').style.display = '';
            document.getElementById('simulateBtn').style.display = '';
            
            if (scriptType === 'sh') {
                // 原生 .sh 脚本：直接预览，无需转换
                writeLog('检测到原生 .sh 脚本，可直接执行', 'ok');
                setModuleStatus('batch', '原生 .sh 脚本：请预览脚本内容，确认后点击「使用此脚本」。', 'ok');
                stepList = [];
                renderSteps();
                // 显示原生SH UI
                document.getElementById('complexScriptBanner').style.display = '';
                document.getElementById('complexScriptBanner').style.background = 'rgba(48,209,88,0.12)';
                document.getElementById('complexScriptBanner').style.borderColor = 'rgba(48,209,88,0.3)';
                document.getElementById('complexScriptBanner').style.color = 'var(--accent-green)';
                document.getElementById('scriptBannerTitle').textContent = '\u2705 检测到原生 .sh 脚本';
                document.getElementById('scriptBannerDesc').textContent = '该脚本原生支持 Termux，可直接执行，无需转换。请预览下方脚本内容，确认无误后点击「使用此脚本」即可开始刷机。';
                document.getElementById('shNativePreviewArea').style.display = '';
                document.getElementById('shNativePreview').textContent = d.content || '';
                document.getElementById('nativeShStatus').textContent = '';
                // 隐藏简单脚本元素
                document.getElementById('stepList').style.display = 'none';
                document.getElementById('toggleStepsBtn').style.display = 'none';
                document.getElementById('simulateBtn').style.display = '';
            } else if (scriptType === 'bat_complex') {
                // 复杂 BAT 脚本：显示原源码 + 手动输入框
                const reason = d.complex_reason || '含循环/条件/子脚本调用';
                writeLog(`检测到复杂 BAT 脚本（${escHtml(reason)}），无法自动解析步骤`, 'warn');
                writeLog(`请查看原脚本源码，手动转换为 .sh 格式后输入`, 'warn');
                setModuleStatus('batch', `复杂 BAT 脚本：${reason}，请手动转换为 .sh`, 'warn');
                stepList = [];
                renderSteps();
                // 显示复杂BAT UI
                document.getElementById('complexScriptBanner').style.display = '';
                document.getElementById('complexScriptBanner').style.background = 'rgba(255,159,10,0.12)';
                document.getElementById('complexScriptBanner').style.borderColor = 'rgba(255,159,10,0.3)';
                document.getElementById('complexScriptBanner').style.color = 'var(--accent-orange)';
                document.getElementById('scriptBannerTitle').textContent = '\u26A0\uFE0F 检测到复杂 BAT 脚本';
                document.getElementById('scriptBannerDesc').textContent = '该脚本包含循环、条件分支或其他复杂语法，无法自动解析为步骤列表。请查看下方原脚本源码，将其手动转换为 Shell (.sh) 格式后输入。';
                document.getElementById('batSourceDetails').style.display = '';
                document.getElementById('batSourceContent').textContent = d.content || '';
                document.getElementById('customScriptArea').style.display = '';
                document.getElementById('customScriptInput').value = '';
                document.getElementById('customScriptStatus').textContent = '';
                // 隐藏简单脚本元素
                document.getElementById('stepList').style.display = 'none';
                document.getElementById('toggleStepsBtn').style.display = 'none';
                document.getElementById('simulateBtn').style.display = '';
            } else {
                // 简单 BAT 脚本：正常流程
                window._isComplexScript = false;
                window._isNativeSh = false;
                window._shContent = '';
                document.getElementById('scriptProcessArea').style.display = 'none';
                document.getElementById('stepList').style.display = '';
                document.getElementById('toggleStepsBtn').style.display = '';
                document.getElementById('simulateBtn').style.display = '';
                
                renderSteps();
                expandStepList();
                // v3.0.6: 缺失文件提醒
                if (d.missing_files && d.missing_files.length > 0) {
                    writeLog('部分镜像文件未找到: ' + d.missing_files.join(', '), 'warn');
                }
                writeLog(`脚本导入成功，共 ${stepList.length} 步`, 'ok');
                document.getElementById('simulateBtn').disabled = stepList.length === 0;
                warnIfScriptHasRebootSteps();
                // 解析成功后自动检测设备
                if (stepList.length > 0) {
                    writeLog('正在自动检测设备...', 'info');
                    document.getElementById('checkDeviceBtn').click();
                }
            }
        } else {
            writeLog('导入失败：' + d.error, 'err');
        }
    } catch(e) { writeLog('导入出错：' + e.message, 'err'); }
    
    document.getElementById('importBatBtn').disabled = false;
};

// v3.0.2: 将步骤列表转换为 .sh 脚本格式，用于统一模拟执行
function stepsToShScript(steps) {
    const lines = ['#!/bin/bash', 'FASTBOOT=${FASTBOOT:-fastboot}'];
    steps.forEach(step => {
        const type = step.type || 'flash';
        const part = step.partition || step.part || '';
        const fileName = step.fileName || step.image || '';
        const params = step.params || '';
        const target = step.target || '';

        if (type === 'flash') {
            lines.push(`$FASTBOOT flash ${part} ${fileName} ${params}`.trim());
        } else if (type === 'erase') {
            lines.push(`$FASTBOOT erase ${part}`);
        } else if (type === 'format') {
            lines.push(`$FASTBOOT format ${part}`);
        } else if (type === 'reboot') {
            lines.push(`$FASTBOOT reboot ${target || part || ''}`.trim());
        } else if (type === 'boot') {
            lines.push(`$FASTBOOT boot ${fileName}`);
        } else if (type === 'oem') {
            lines.push(`$FASTBOOT oem ${target || part || ''}`.trim());
        } else if (type === 'flashing') {
            lines.push(`$FASTBOOT flashing ${target || part || ''}`.trim());
        } else if (type === 'set_active') {
            lines.push(`$FASTBOOT set_active ${target || part || 'a'}`.trim());
        } else if (type === 'delete-logical-partition') {
            lines.push(`$FASTBOOT delete-logical-partition ${part}`);
        } else if (type === 'resize-partition') {
            lines.push(`$FASTBOOT resize-partition ${part} ${step.size || ''}`.trim());
        } else if (type === 'getvar') {
            lines.push(`$FASTBOOT getvar ${part}`);
        } else if (type === 'devices') {
            lines.push(`$FASTBOOT devices`);
        } else if (step.raw) {
            lines.push(step.raw);
        }
    });
    return lines.join('\n');
}

// v3.0.2: 模拟运行 - 统一所有脚本类型的模拟执行路径
document.getElementById('simulateBtn').onclick = async () => {
    // 获取要模拟的脚本内容
    let shContent = '';
    let simLabel = '';

    if ((window._isComplexScript || window._isNativeSh) && window._shContent) {
        // 复杂/原生 .sh 模式：使用用户确认的脚本内容
        shContent = window._shContent;
        simLabel = window._isNativeSh ? '原生 .sh 脚本' : '复杂脚本';
    } else if (stepList.length > 0) {
        // 简单脚本模式：将步骤列表转换为 .sh 脚本
        shContent = stepsToShScript(stepList);
        simLabel = '简单脚本（步骤列表）';
    } else {
        writeLog('没有可模拟的脚本或步骤', 'err');
        return;
    }

    writeLog('开始模拟刷入（' + simLabel + ' dry_run 模式）...', 'warn');
    setModuleStatus('batch', '模拟刷入中...', 'info');
    showModuleProgress('batch', '模拟执行');
    document.getElementById('simulateBtn').disabled = true;
    try {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), 30000);
        const d = await parseApiResponse(await fetch((window.BACKEND_API_URL || '') + '/api/batch-task/direct_execute', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                sh_content: shContent,
                rom_name: getSelectedRomProject(),
                dry_run: true
            }),
            signal: ctrl.signal
        }), '/api/batch-task/direct_execute');
        clearTimeout(timer);
        if (d.success) {
            writeLog('模拟刷入已启动，任务ID: ' + d.task_id, 'ok');
            pollDirectExecuteTask(d.task_id);
        } else {
            writeLog('模拟刷入失败：' + (d.error || '未知错误'), 'err');
            document.getElementById('simulateBtn').disabled = false;
        }
    } catch(e) {
        writeLog('模拟刷入出错：' + e.message, 'err');
        document.getElementById('simulateBtn').disabled = false;
    }
};

function renderSteps() {
    stepListEl.innerHTML = '';

    if (stepList.length === 0) {
        stepListEl.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted)">解析脚本生成步骤</div>';
        updateBatchSummary();
        updateBtnState();
        return;
    }

    // 使用 DocumentFragment 减少 DOM 重排
    const frag = document.createDocumentFragment();
    stepList.forEach((item, idx) => {
        const d = document.createElement('div');
        d.className = 'step-item';
        
        let lab, cls, cont, badge = '';
        switch(item.type) {
            case 'flash':
                lab = '刷写'; cls = 'type-flash';
                cont = `${escHtml(item.part)} → ${escHtml(item.fileName)} ${escHtml(item.params||'')}`;
                if (item.prefixParams && (item.prefixParams.includes('disable-verity') || item.prefixParams.includes('disable-verification'))) {
                    badge = '<span class="step-badge badge-avb">禁用AVB</span>';
                }
                break;
            case 'erase':
                lab = '擦除'; cls = 'type-erase'; cont = escHtml(item.part);
                if (item.cow_cleanup) {
                    badge = '<span class="step-badge badge-cow">COW动态清理</span>';
                }
                break;
            case 'set_active': lab = '设槽位'; cls = 'type-set'; cont = `激活 ${escHtml(item.part)}`; break;
            case 'reboot': lab = '重启'; cls = 'type-reboot'; cont = escHtml(item.part) || '系统'; break;
        }
        
        if (item.condition) {
            badge += '<span class="step-badge badge-cond">条件执行</span>';
        }
        if (item.loop) {
            badge += '<span class="step-badge badge-loop">循环展开</span>';
        }
        
        d.innerHTML = `<span class="idx">${idx+1}</span><span class="type ${cls}">${lab}</span><span>${cont}</span>${badge}<button class="del-btn" data-idx="${idx}">删除</button>`;
        frag.appendChild(d);
    });
    stepListEl.appendChild(frag);
    
    stepListEl.querySelectorAll('.del-btn').forEach(b => {
        b.onclick = e => {
            stepList.splice(+e.target.dataset.idx, 1);
            renderSteps();
        };
    });
    
    updateBatchSummary();
    updateRiskSummary();
    updateResumeCard();
    updateBtnState();
}

document.getElementById('toggleStepsBtn').onclick = () => {
    stepListEl.classList.toggle('collapsed');
    document.getElementById('toggleStepsBtn').textContent = stepListEl.classList.contains('collapsed') ? '查看步骤 ▾' : '收起步骤 ▴';
    localStorage.setItem('steps_expanded', stepListEl.classList.contains('collapsed') ? '0' : '1');
};

function expandStepList() {
    if (stepList.length === 0) return;
    stepListEl.classList.remove('collapsed');
    document.getElementById('toggleStepsBtn').textContent = '收起步骤 ▴';
    localStorage.setItem('steps_expanded', '1');
}

document.getElementById('clearBatchStepsBtn').onclick = () => {
    stepList = [];
    localStorage.removeItem('batch_progress');
    clearReconnectCheckpoint();
    document.getElementById('exportBatchLogBtn').style.display = 'none';

    batchTip.textContent = '';
    hideModuleProgress('batch');
    setModuleStatus('batch', appRunMode === 'webusb'
        ? '线刷状态：WebUSB模式等待解析刷机脚本。'
        : '线刷状态：等待解析脚本并检测设备。', 'info');
    renderSteps();
    writeLog('已清空线刷步骤', 'info');
    updateResumeCard();

    // 隐藏复杂脚本模式的所有新增元素
    ['scriptProcessArea', 'complexScriptBanner', 'batSourceDetails', 'shNativePreviewArea', 'customScriptArea', 'riskSummaryCard'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
    // 恢复简单脚本模式 UI
    document.getElementById('stepList').style.display = '';
    document.getElementById('toggleStepsBtn').style.display = '';
    document.getElementById('simulateBtn').style.display = '';
    window._isComplexScript = false;
    window._isNativeSh = false;
    window._scriptType = '';
    window._shContent = '';
    window._customScriptPath = '';
    window._batSourceContent = '';
};

document.getElementById('resumeFlashBtn').onclick = () => {
    const saved = localStorage.getItem('batch_progress');
    if (!saved) return;
    const data = JSON.parse(saved);
    if (data.rom_name) document.getElementById('romProjectSelect').value = data.rom_name;
    stepList = data.steps || [];
    pendingResumeIndex = Number(data.step_index || 0);
    renderSteps();
    writeLog(`已加载断点，将从第 ${pendingResumeIndex + 1} 步继续`, 'tip');
    startFlashFromIndex(pendingResumeIndex);
};
document.getElementById('restartFlashBtn').onclick = () => {
    localStorage.removeItem('batch_progress');
    clearReconnectCheckpoint();
    document.getElementById('exportBatchLogBtn').style.display = 'none';
    pendingResumeIndex = 0;
    updateResumeCard();
    startFlashFromIndex(0);
};

// 导出日志按钮
document.getElementById('exportBatchLogBtn').onclick = async () => {
    try {
        const res = await apiGet('/api/batch-task/export_log');
        if (res.success) {
            const blob = new Blob([res.content], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = res.filename || 'flash_log.txt';
            a.click();
            URL.revokeObjectURL(url);
        } else {
            showToast(res.error || '没有可导出的日志');
        }
    } catch (e) {
        writeLog('导出日志失败: ' + e, 'err');
    }
};
document.getElementById('clearResumeBtn').onclick = () => {
    localStorage.removeItem('batch_progress');
    clearReconnectCheckpoint();
    pendingResumeIndex = 0;
    updateResumeCard();
    writeLog('已清除断点记录', 'info');
};