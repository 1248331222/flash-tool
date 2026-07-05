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
            window._shContent = '';
            window._batSourceContent = d.content || '';
            window._hydraSummary = d.hydra_summary || null;
            window._isComplexScript = false;
            window._isNativeSh = false;
            window._scriptType = '';
            
            // 隐藏复杂/原生脚本相关UI
            document.getElementById('scriptProcessArea').style.display = 'none';
            document.getElementById('complexScriptBanner').style.display = 'none';
            document.getElementById('batSourceDetails').style.display = 'none';
            document.getElementById('shNativePreviewArea').style.display = 'none';
            document.getElementById('customScriptArea').style.display = 'none';
            
            if (stepList.length > 0) {
                // 有解析步骤 → 显示步骤列表
                document.getElementById('stepList').style.display = '';
                document.getElementById('toggleStepsBtn').style.display = '';
                document.getElementById('simulateBtn').style.display = '';
                renderSteps();
                expandStepList();
                if (d.missing_files && d.missing_files.length > 0) {
                    writeLog('部分镜像文件未找到: ' + d.missing_files.join(', '), 'warn');
                }
                writeLog(`脚本导入成功，共 ${stepList.length} 步`, 'ok');
                document.getElementById('simulateBtn').disabled = stepList.length === 0;
                warnIfScriptHasRebootSteps();
                // 自动检测设备
                if (stepList.length > 0) {
                    writeLog('正在自动检测设备...', 'info');
                    document.getElementById('checkDeviceBtn').click();
                }
            } else {
                // 无步骤（回退旧版解析器返回空等）→ 显示原始内容
                writeLog('脚本解析后无可用步骤，显示原始脚本内容', 'warn');
                setModuleStatus('batch', '脚本解析为空，请检查脚本内容', 'warn');
                document.getElementById('stepList').style.display = '';
                renderSteps();
                document.getElementById('simulateBtn').style.display = 'none';
                document.getElementById('toggleStepsBtn').style.display = 'none';
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
            const imgPath = step.imagePath || step.fileName || '';
            lines.push(`$FASTBOOT flash ${part} ${imgPath} ${params}`.trim());
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

// v3.0.2: 模拟运行 - 步骤列表转脚本模拟
document.getElementById('simulateBtn').onclick = async () => {
    if (stepList.length === 0) {
        writeLog('没有可模拟的步骤', 'err');
        return;
    }
    const shContent = stepsToShScript(stepList);
    writeLog('开始模拟刷入（步骤列表 dry_run 模式）...', 'warn');
    setModuleStatus('batch', '模拟刷入中...', 'info');
    showModuleProgress('batch', '模拟执行');
    document.getElementById('simulateBtn').disabled = true;
    try {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), 30000);
        const d = await parseApiResponse(await fetch((App.backendUrl || '') + '/api/batch-task/direct_execute', {
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
                const displayPath = item.imagePath || item.fileName || '';
                const isWildcard = (item.part || '').includes('%%') || (displayPath || '').includes('%%');
                if (isWildcard) {
                    lab = '刷写(循环)'; 
                    const partBase = (item.part || '').replace(/%%~nf_([ab])/, '分区_$1');
                    cont = `${escHtml(partBase)} ← ${escHtml(displayPath)}`;
                    badge = '<span class="step-badge badge-loop">循环展开</span>';
                } else {
                    cont = `${escHtml(item.part)} → ${escHtml(displayPath)} ${escHtml(item.params||'')}`;
                }
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
            case 'reboot': lab = '重启'; cls = 'type-reboot'; cont = '重启到 ' + ((item.part && escHtml(item.part)) || '系统'); break;
            case 'devices': lab = '检测'; cls = 'type-devices'; cont = '等待设备连接'; break;
            case 'oem': lab = 'OEM'; cls = 'type-oem'; cont = escHtml(item.part) || '命令'; break;
            case 'flashing': lab = '解锁'; cls = 'type-flashing'; cont = escHtml(item.part) || ''; break;
            case 'update': lab = '更新'; cls = 'type-update'; cont = 'fastboot update'; break;
            case 'boot': lab = '启动'; cls = 'type-boot'; cont = escHtml(item.fileName) || ''; break;
            case 'format': lab = '格式化'; cls = 'type-format'; cont = escHtml(item.part) || ''; break;
            case 'getvar': lab = '查询'; cls = 'type-getvar'; cont = escHtml(item.part) || ''; break;
            case 'adb': lab = 'ADB'; cls = 'type-adb'; cont = escHtml(item.raw) || ''; break;
            case 'delete-logical-partition': lab = '删分区'; cls = 'type-erase'; cont = escHtml(item.part) || ''; badge = '<span class="step-badge badge-cow">COW</span>'; break;
            default:
                lab = '其他'; cls = 'type-other';
                cont = escHtml(item.type || '') + ' ' + escHtml(item.part || '') + ' ' + escHtml(item.raw || '').substring(0, 60);
                break;
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
    window._hydraSummary = null;
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