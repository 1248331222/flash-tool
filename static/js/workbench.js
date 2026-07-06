// flash_tool/static/js/workbench.js
// ============ 工作台 v3.2.0 ============
// 注：wbSteps / wbExecuting / wbDetectedPartitions / wbCurrentType 已在 state.js 中声明

// 快捷操作折叠/展开
// 快捷操作分类切换（按钮模式：同类toggle，异类切换）
function wbToggleQA(type) {
    const tabFb = document.getElementById('wbQATabFb');
    const tabAdb = document.getElementById('wbQATabAdb');
    const secFb = document.getElementById('wbQAFb');
    const secAdb = document.getElementById('wbQAAdb');
    if (!tabFb || !tabAdb || !secFb || !secAdb) return;
    if (type === 'fb') {
        const isShow = secFb.style.display !== 'none';
        secFb.style.display = isShow ? 'none' : '';
        secAdb.style.display = 'none';
        tabFb.className = isShow ? 'wb-qa-tab' : 'wb-qa-tab active-fb';
        tabAdb.className = 'wb-qa-tab';
    } else {
        const isShow = secAdb.style.display !== 'none';
        secAdb.style.display = isShow ? 'none' : '';
        secFb.style.display = 'none';
        tabAdb.className = isShow ? 'wb-qa-tab' : 'wb-qa-tab active-adb';
        tabFb.className = 'wb-qa-tab';
    }
}

// 步骤类型切换（按钮模式）
function wbSwitchType(type) {
    wbCurrentType = type;
    document.querySelectorAll('.wb-type-btn').forEach(b => b.classList.toggle('active', b.dataset.type === type));
    document.getElementById('wbAddFastboot').style.display = type === 'fastboot' ? '' : 'none';
    document.getElementById('wbAddAdb').style.display = type === 'adb' ? '' : 'none';
    document.getElementById('wbAddFastbootCmd').style.display = type === 'fastbootcmd' ? '' : 'none';
}

// 分区名来源切换
function wbPartSourceChange() {
    const v = document.getElementById('wbPartSource').value;
    document.getElementById('wbPartDetected').style.display = v === 'detected' ? '' : 'none';
    document.getElementById('wbPartCustom').style.display = v === 'custom' ? '' : 'none';
}

// 镜像来源切换
function wbImgSourceChange() {
    const v = document.getElementById('wbImgSource').value;
    document.getElementById('wbImgRomRow').style.display = v === 'rom' ? '' : 'none';
    document.getElementById('wbImgCustomRow').style.display = v === 'custom' ? '' : 'none';
    if (v === 'rom') wbLoadRomPackages();
}

// 加载线刷包列表
async function wbLoadRomPackages() {
    try {
        const d = await apiGet('/api/rom/list');
        const sel = document.getElementById('wbRomSelect');
        sel.innerHTML = '<option value="">选择已解压线刷包</option>';
        if (d.dirs && d.dirs.length) d.dirs.forEach(item => { const name = typeof item === 'object' ? item.name : item; const o = document.createElement('option'); o.value = name; o.textContent = name; sel.appendChild(o); });
    } catch(e) {}
}

// 加载线刷包镜像列表
async function wbLoadRomImages() {
    const rn = document.getElementById('wbRomSelect').value;
    const sel = document.getElementById('wbRomImgSelect');
    if (!rn) { sel.innerHTML = '<option value="">请先选择线刷包</option>'; return; }
    try {
        sel.innerHTML = '<option value="">加载中...</option>';
        const d = await apiGet(`/api/rom/images?rom_name=${encodeURIComponent(rn)}`);
        if (d.success) {
            sel.innerHTML = '<option value="">选择镜像</option>';
            if (d.files) d.files.forEach(f => { const o = document.createElement('option'); o.value = f; o.textContent = f; sel.appendChild(o); });
        }
    } catch(e) { sel.innerHTML = '<option value="">加载失败</option>'; }
}

// 检测分区
async function wbDetectPartitions() {
    writeLog('工作台：正在检测设备分区...', 'info');
    try {
        const res = await apiPost('/api/fastboot', {args: ['getvar', 'partition-size:all']});
        const text = (res.output || res.combined || '');
        const parts = [];
        text.split('\n').forEach(line => {
            const m = line.match(/partition-size:(\S+)/);
            if (m && m[1] !== '(invalid') parts.push(m[1]);
        });
        wbDetectedPartitions = parts.sort();
        const sel = document.getElementById('wbPartSelect');
        sel.innerHTML = '';
        if (parts.length === 0) { sel.innerHTML = '<option value="">未检测到分区</option>'; writeLog('未检测到分区', 'warn'); return; }
        parts.forEach(p => { const o = document.createElement('option'); o.value = p; o.textContent = p; sel.appendChild(o); });
        writeLog(`工作台：检测到 ${parts.length} 个分区`, 'ok');
    } catch(e) { writeLog('分区检测失败: ' + e.message, 'err'); }
}

// 获取当前分区名
function wbGetCurrentPartName() {
    if (document.getElementById('wbPartSource').value === 'detected') {
        return document.getElementById('wbPartSelect').value;
    }
    return document.getElementById('wbPartName').value.trim();
}

// 获取当前镜像路径
function wbGetCurrentImagePath() {
    const src = document.getElementById('wbImgSource').value;
    if (src === 'rom') return document.getElementById('wbRomImgSelect').value;
    if (src === 'custom') return document.getElementById('wbImgCustomPath').value.trim();
    return '';
}

// 快捷操作 - 直接指定工具类型和命令，无需模式判断
function wbQuickAction(type, cmd, desc, risk) {
    const raw = type + ' ' + cmd;
    // command 取第一个有意义的参数（非 -- 开头），用于后端识别工具子命令
    const firstArg = cmd.split(' ').find(a => a && !a.startsWith('-')) || cmd.split(' ')[0];
    wbSteps.push({id: Date.now(), type: type, command: firstArg, args: cmd, raw, desc: desc, risk: risk || 'safe', status: 'pending', enabled: true});
    renderWbSteps();
    writeLog(`工作台：${desc}`, 'info');
}

// 快捷操作 - 需要参数输入的版本
function wbQuickActionNeedsArg(type, cmd, desc, argLabel, risk) {
    const arg = prompt(`${desc}\n请输入${argLabel}：`);
    if (!arg) return;
    const actualCmd = cmd.replace('__ARG__', arg);
    const raw = type + ' ' + actualCmd;
    wbSteps.push({id: Date.now(), type: type, command: actualCmd.split(' ')[0], args: actualCmd, raw, desc: desc, risk: risk || 'warn', status: 'pending', enabled: true});
    renderWbSteps();
    writeLog(`工作台：${desc}`, 'info');
}

// 添加 Fastboot 步骤
function wbAddFastbootStep() {
    const part = wbGetCurrentPartName();
    if (!part) return writeLog('请填写或选择分区名', 'err');
    const imgSrc = document.getElementById('wbImgSource').value;
    const img = wbGetCurrentImagePath();
    const extra = document.getElementById('wbFbExtra').value.trim();
    let raw, desc;
    if (img) {
        if (extra) raw = 'fastboot ' + extra + ' flash ' + part + ' ' + img;
        else raw = 'fastboot flash ' + part + ' ' + img;
        desc = `刷入 ${part} 分区（镜像: ${img.split('/').pop()}）`;
    } else {
        if (extra) raw = 'fastboot ' + extra + ' ' + part;
        else raw = 'fastboot flash ' + part;
        desc = `操作 ${part} 分区`;
    }
    wbSteps.push({id: Date.now(), type: 'fastboot', command: 'flash', args: part + (img ? ' ' + img : ''), raw, desc, risk: 'danger', status: 'pending', enabled: true, imgSource: imgSrc, romName: document.getElementById('wbRomSelect').value || ''});
    renderWbSteps();
    if (document.getElementById('wbPartSource').value === 'custom') document.getElementById('wbPartName').value = '';
    document.getElementById('wbFbExtra').value = '';
    writeLog(`工作台：${desc}`, 'info');
}

// 添加 ADB 步骤
function wbAddAdbStep() {
    const args = document.getElementById('wbAdbArgs').value.trim();
    if (!args) return writeLog('请输入ADB参数', 'err');
    const raw = 'adb ' + args;
    wbSteps.push({id: Date.now(), type: 'adb', command: args.split(' ')[0], args, raw, desc: wbDescribe(raw), status: 'pending', enabled: true});
    renderWbSteps();
    document.getElementById('wbAdbArgs').value = '';
    writeLog(`工作台：${wbDescribe(raw)}`, 'info');
}

// 添加 Fastboot 自定义命令步骤
function wbAddFastbootCmdStep() {
    const args = document.getElementById('wbFastbootCmdArgs').value.trim();
    if (!args) return writeLog('请输入fastboot参数', 'err');
    const raw = 'fastboot ' + args;
    wbSteps.push({id: Date.now(), type: 'fastboot', command: args.split(' ')[0], args, raw, desc: wbDescribe(raw), status: 'pending', enabled: true});
    renderWbSteps();
    document.getElementById('wbFastbootCmdArgs').value = '';
    writeLog(`工作台：${wbDescribe(raw)}`, 'info');
}

// 步骤描述生成（中文人性化）
function wbDescribe(raw) {
    const r = raw.trim();
    const rl = r.toLowerCase();
    // Fastboot 命令
    const fbFlash = rl.match(/^fastboot\s+(?:--?\S+\s+)*flash\s+(\S+)\s+(\S+)/);
    if (fbFlash) return `刷入 ${fbFlash[1]} 分区（镜像: ${fbFlash[2].split('/').pop()}）`;
    const fbErase = rl.match(/^fastboot\s+erase\s+(\S+)/);
    if (fbErase) {
        const p = fbErase[1].toLowerCase();
        if (p === 'userdata') return '擦除 userdata 分区（数据丢失）';
        if (p === 'cache') return '擦除 cache 分区';
        return `擦除 ${fbErase[1]} 分区`;
    }
    if (/^fastboot\s+-w/.test(rl)) return '双清（擦除 userdata + cache，数据丢失）';
    const fbFormat = rl.match(/^fastboot\s+format\s+(\S+)/);
    if (fbFormat) return `格式化 ${fbFormat[1]} 分区`;
    const fbSetA = rl.match(/^fastboot\s+set_active\s+(\S+)/);
    if (fbSetA) return `切换到 ${fbSetA[1].toUpperCase()} 槽`;
    if (/^fastboot\s+reboot\s*$/.test(rl)) return '重启到系统';
    if (/^fastboot\s+reboot\s+bootloader/.test(rl)) return '进入 Bootloader';
    if (/^fastboot\s+reboot\s+fastboot/.test(rl)) return '进入 Fastbootd';
    if (/^fastboot\s+reboot\s+recovery/.test(rl)) return '进入 Recovery';
    if (/^fastboot\s+flashing\s+unlock/.test(rl)) return '解锁 Bootloader（清除数据）';
    if (/^fastboot\s+flashing\s+lock/.test(rl)) return '上锁 Bootloader';
    if (/^fastboot\s+flashing\s+get_unlock_ability/.test(rl)) return '查询解锁能力';
    const fbBoot = rl.match(/^fastboot\s+boot\s+(\S+)/);
    if (fbBoot) return `临时启动 ${fbBoot[1].split('/').pop()}`;
    if (/^fastboot\s+getvar\s+all/.test(rl)) return '查询全部设备变量';
    if (/^fastboot\s+getvar\s+(\S+)/.test(rl)) return `查询设备变量: ${rl.match(/^fastboot\s+getvar\s+(\S+)/)[1]}`;
    if (/^fastboot\s+devices/.test(rl)) return '列出 Fastboot 设备';
    if (/^fastboot\s+snapshot-update\s+cancel/.test(rl)) return '取消 Virtual A/B 更新';
    // ADB 命令
    if (/^adb\s+devices/.test(rl)) return '列出 ADB 设备';
    if (/^adb\s+reboot\s+bootloader/.test(rl)) return '通过 ADB 进入 Bootloader';
    if (/^adb\s+reboot\s+fastboot/.test(rl)) return '通过 ADB 进入 Fastbootd';
    if (/^adb\s+reboot\s+recovery/.test(rl)) return '通过 ADB 进入 Recovery';
    if (/^adb\s+reboot\s*$/.test(rl)) return '通过 ADB 重启系统';
    if (/^adb\s+install/.test(rl)) return `安装应用 ${r.match(/adb\s+install\s+(?:-r\s+)?(\S+)/)?.[1]||''}`;
    if (/^adb\s+uninstall/.test(rl)) return `卸载应用 ${r.match(/adb\s+uninstall\s+(?:-k\s+)?(\S+)/)?.[1]||''}`;
    if (/^adb\s+shell\s+pm\s+clear/.test(rl)) return `清除应用数据 ${r.match(/adb\s+shell\s+pm\s+clear\s+(\S+)/)?.[1]||''}`;
    if (/^adb\s+push/.test(rl)) return `推送文件到设备`;
    if (/^adb\s+pull/.test(rl)) return `从设备拉取文件`;
    if (/^adb\s+sideload/.test(rl)) return `侧载刷入 ${r.match(/adb\s+sideload\s+(\S+)/)?.[1]||''}`;
    return r;
}

// 风险评级
function wbGetRisk(s) {
    if (s.risk) return s.risk;
    const rl = s.raw.toLowerCase();
    if (/erase\s+userdata|format\s+userdata|^-w|flashing\s+unlock/.test(rl)) return s.type === 'fastboot' ? 'data-loss' : 'danger';
    if (/flash\s+(boot|bootloader|system|vendor|modem|xbl|partition)/.test(rl)) return 'danger';
    if (/erase\s+cache|reboot|set_active/.test(rl)) return 'warn';
    return 'safe';
}

// 渲染步骤列表
function renderWbSteps() {
    const el = document.getElementById('wbStepList');
    const countEl = document.getElementById('wbStepCount');
    if (countEl) countEl.textContent = wbSteps.length ? `(${wbSteps.length}步)` : '';
    if (wbSteps.length === 0) {
        el.innerHTML = '<div class="empty-state">暂无步骤，请添加 Fastboot/ADB/Shell 命令。</div>';
        return;
    }
    el.innerHTML = '';
    wbSteps.forEach((s, i) => {
        const d = document.createElement('div');
        d.className = 'wb-step';
        d.setAttribute('data-type', s.type);
        const desc = s.desc || wbDescribe(s.raw);
        const risk = wbGetRisk(s);
        const riskLabel = risk === 'safe' ? '' : risk === 'warn' ? ' ⚠️' : risk === 'danger' ? ' 🔴' : ' 💀';
        d.innerHTML = `
            <span class="wb-step-num">${i+1}</span>
            <button class="wb-up-btn" title="上移" ${i===0?'disabled':''}>▲</button>
            <button class="wb-down-btn" title="下移" ${i===wbSteps.length-1?'disabled':''}>▼</button>
            <div style="flex:1;min-width:0">
                <div class="wb-step-desc">${escHtml(desc)}<span class="wb-step-risk ${risk}">${riskLabel}</span></div>
                <div class="wb-step-raw">${escHtml(s.raw)}</div>
            </div>
            <span class="wb-status ${s.status}">${s.status==='pending'?'等待':s.status==='running'?'执行中':s.status==='success'?'✓':s.status==='failed'?'✗':s.status}</span>
            <span class="wb-step-actions">
                <button class="wb-run-btn" ${wbExecuting?'disabled':''}>▶</button>
                <button class="wb-del-btn">✕</button>
            </span>`;
        el.appendChild(d);
        d.querySelector('.wb-up-btn').onclick = () => { if(i>0){[wbSteps[i],wbSteps[i-1]]=[wbSteps[i-1],wbSteps[i]];renderWbSteps();}};
        d.querySelector('.wb-down-btn').onclick = () => { if(i<wbSteps.length-1){[wbSteps[i],wbSteps[i+1]]=[wbSteps[i+1],wbSteps[i]];renderWbSteps();}};
        d.querySelector('.wb-run-btn').onclick = () => wbRunSingle(i);
        d.querySelector('.wb-del-btn').onclick = () => { wbSteps.splice(i,1); renderWbSteps(); };
    });
}

// 生成脚本（支持相对路径）
function wbGenerateScript() {
    if (wbSteps.length === 0) return '#!/bin/bash\n# 工作台：无步骤\n';
    const romName = wbSteps.find(s => s.romName)?.romName || '';
    let sh = '#!/bin/bash\n';
    sh += `# Termux 刷机工具 - 工作台自动生成\n`;
    sh += `# 生成时间: ${new Date().toLocaleString()}\n`;
    sh += `# 步骤数: ${wbSteps.length}\n\n`;
    sh += `export FASTBOOT="$FASTBOOT"\nexport ADB="$ADB"\n`;
    if (romName) sh += `export ROM_DIR="$HOME/storage/shared/123456/rom/${romName}"\ncd "$ROM_DIR"\n\n`;
    let idx = 0;
    const enabled = wbSteps.filter(s => s.enabled);
    enabled.forEach(s => {
        idx++;
        sh += `# [${idx}/${enabled.length}] ${s.raw}\n`;
        sh += `${s.raw}\n\n`;
        if (s.type === 'fastboot' && s.raw.toLowerCase().match(/reboot\s+(bootloader|fastboot)/)) {
            sh += `echo "等待设备重连..."\nsleep 5\nwhile ! $FASTBOOT devices 2>/dev/null | grep -q "fastboot"; do sleep 2; done\n\n`;
        }
    });
    return sh;
}

// 导出/复制/下载脚本
function wbExportScript() { document.getElementById('wbScriptCode').textContent = wbGenerateScript(); document.getElementById('wbScriptPreview').style.display = ''; }
async function wbCopyScript() { try { await navigator.clipboard.writeText(wbGenerateScript()); showToast('脚本已复制到剪贴板'); } catch(e) { writeLog('复制失败: ' + e.message, 'err'); } }
function wbDownloadScript() { const b = new Blob([wbGenerateScript()],{type:'application/x-sh'}); const u = URL.createObjectURL(b); const a = document.createElement('a'); a.href=u; a.download=`flash_workbench_${Date.now()}.sh`; a.click(); URL.revokeObjectURL(u); }
// 全部执行
async function wbRunAll(dryRun = false) {
    if (wbSteps.length === 0) return writeLog('请先添加步骤', 'err');
    if (wbExecuting) return;

    const enabledSteps = wbSteps.filter(s => s.enabled);
    if (enabledSteps.length === 0) return writeLog('没有启用的步骤', 'err');

    // 生成脚本
    const script = wbGenerateScript();

    wbExecuting = true;
    renderWbSteps();
    writeLog('工作台：开始执行全部步骤...', 'info');
    showModuleProgress('wb', dryRun ? '模拟执行' : '执行');

    try {
        const res = await apiPost('/api/batch-task/direct_execute', {
            sh_content: script,
            rom_name: wbSteps.find(s => s.romName)?.romName || '',
            dry_run: !!dryRun
        });

        if (res.success && res.task_id) {
            writeLog('工作台：任务已启动，等待执行完成...', 'info');
            // 轮询任务状态
            let pollFailedCount = 0;
            const MAX_POLL_FAILURES = 5;
            const pollWb = async () => {
                try {
                    const statusRes = await apiGet(`/api/batch-task/status/${res.task_id}`);
                    const t = statusRes.task;
                    if (!t) { setTimeout(pollWb, 1500); return; }

                    if (t.status === 'completed') {
                        wbSteps.forEach(s => { if (s.enabled) s.status = 'success'; });
                        wbExecuting = false;
                        renderWbSteps();
                        writeLog('工作台：全部步骤执行完成', 'ok');
                        showToast('执行完成');
                        hideModuleProgress('wb');
                    } else if (t.status === 'failed') {
                        wbSteps.forEach(s => { if (s.enabled && s.status === 'running') s.status = 'failed'; });
                        wbExecuting = false;
                        renderWbSteps();
                        writeLog('工作台：执行失败：' + (t.error || '未知错误'), 'err');
                        hideModuleProgress('wb');
                    } else {
                        // 更新当前执行步骤状态
                        if (t.current_index != null && t.current_index < wbSteps.length) {
                            wbSteps.forEach((s, i) => {
                                if (s.enabled) {
                                    if (i < t.current_index) s.status = 'success';
                                    else if (i === t.current_index) s.status = 'running';
                                    else s.status = 'pending';
                                }
                            });
                            renderWbSteps();
                        }
                        if (t.progress != null) updateModuleProgress('wb', t.progress, '');
                        setTimeout(pollWb, 1500);
                    }
                } catch(e) {
                    pollFailedCount++;
                    writeLog('工作台：轮询失败(' + pollFailedCount + '/' + MAX_POLL_FAILURES + ')：' + e.message, 'err');
                    if (pollFailedCount >= MAX_POLL_FAILURES) {
                        wbExecuting = false;
                        renderWbSteps();
                        writeLog('工作台：轮询连续失败，已停止自动检测。请手动刷新任务状态。', 'err');
                        hideModuleProgress('wb');
                    } else {
                        setTimeout(pollWb, 3000);
                    }
                }
            };
            pollWb();
        } else {
            wbExecuting = false;
            renderWbSteps();
            writeLog('工作台：启动失败：' + (res.error || '未知错误'), 'err');
        }
    } catch(e) {
        wbExecuting = false;
        renderWbSteps();
        writeLog('工作台：执行错误：' + e.message, 'err');
    }
}

// 单步执行
async function wbRunSingle(idx) {
    if (wbExecuting) return;
    const s = wbSteps[idx]; if (!s) return;
    s.status = 'running'; renderWbSteps();
    setModuleStatus('wb', `执行步骤 ${idx+1}: ${s.desc||s.raw}`, 'info');
    try {
        const tool = s.type === 'fastboot' ? 'fastboot' : (s.type === 'adb' ? 'adb' : '');
        let url, body;
        if (tool) { url = tool==='adb'?'/api/adb':'/api/fastboot'; body = {args: s.raw.replace(/^fastboot\s+/, '').replace(/^adb\s+/, '').split(' ')}; }
        else { url = '/api/shell/run_single'; body = {command: s.raw, timeout: 120}; }
        const res = await apiPost(url, body);
        s.status = res.success ? 'success' : 'failed';
        const output = res.output || res.combined || res.error || '';
        writeLog(`[${s.status==='success'?'✓':'✗'}] ${s.desc||s.raw} → ${output.split('\n')[0]}`, s.status==='success'?'ok':'err');
    } catch(e) { s.status = 'failed'; writeLog(`[${idx+1}] ${s.raw} → 异常：${e.message}`, 'err'); }
    renderWbSteps();
}

// 清空
function wbClearSteps() {
    if (wbSteps.length === 0) return;
    showConfirm('清空确认', '确定要清空所有步骤吗？', () => { wbSteps = []; renderWbSteps(); writeLog('工作台：已清空所有步骤', 'info'); });
}

// 保存方案
function wbSaveScheme() {
    if (wbSteps.length === 0) return writeLog('工作台：无步骤可保存', 'err');
    const name = prompt('请输入方案名称：', '我的刷机方案');
    if (!name) return;
    let schemes;
    try { schemes = JSON.parse(localStorage.getItem('wb_schemes') || '[]'); }
    catch(e) { schemes = []; }
    schemes.push({name, steps: wbSteps.map(s=>({...s, status:'pending'})), saved_at: new Date().toISOString()});
    localStorage.setItem('wb_schemes', JSON.stringify(schemes));
    writeLog(`工作台：方案「${name}」已保存（${wbSteps.length}步）`, 'ok');
    showToast('方案已保存');
}

// 方案管理面板
function wbManageSchemes() {
    const panel = document.getElementById('wbSchemePanel');
    if (!panel) return;
    let schemes;
    try { schemes = JSON.parse(localStorage.getItem('wb_schemes') || '[]'); }
    catch(e) { schemes = []; }
    const list = document.getElementById('wbSchemeList');
    list.innerHTML = '';
    if (schemes.length === 0) {
        list.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:20px">暂无已保存方案</div>';
    } else {
        schemes.forEach((s, i) => {
            const item = document.createElement('div');
            item.className = 'wb-scheme-item';
            item.innerHTML = `<div><div style="font-size:13px">${escHtml(s.name)}</div><div style="font-size:11px;color:var(--text-muted)">${s.steps.length}步 · ${s.saved_at.slice(0,10)}</div></div><div><button class="btn small" onclick="wbLoadSchemeById(${i})" style="margin-right:4px">加载</button><button class="btn small danger" onclick="wbDeleteScheme(${i})">删除</button></div>`;
            list.appendChild(item);
        });
    }
    panel.classList.add('show');
}
function wbCloseSchemePanel() { document.getElementById('wbSchemePanel').classList.remove('show'); }
function wbLoadSchemeById(idx) {
    let schemes;
    try { schemes = JSON.parse(localStorage.getItem('wb_schemes') || '[]'); }
    catch(e) { schemes = []; }
    if (idx >= 0 && idx < schemes.length) {
        wbSteps = schemes[idx].steps.map(s => ({...s, status: 'pending'}));
        renderWbSteps();
        writeLog(`工作台：已加载方案「${schemes[idx].name}」`, 'ok');
        wbCloseSchemePanel();
    }
}
function wbDeleteScheme(idx) {
    let schemes;
    try { schemes = JSON.parse(localStorage.getItem('wb_schemes') || '[]'); }
    catch(e) { schemes = []; }
    const name = schemes[idx]?.name || '';
    wbCloseSchemePanel();
    showConfirm('删除确认', `确定要删除方案「${name}」吗？`, () => {
        schemes.splice(idx, 1);
        localStorage.setItem('wb_schemes', JSON.stringify(schemes));
        writeLog(`工作台：方案「${name}」已删除`, 'info');
    });
}

// 加载方案（旧函数保留兼容，改为打开管理面板）
function wbLoadScheme() { wbManageSchemes(); }

// 初始化：加载线刷包列表
(function wbInit() {
    if (document.getElementById('wbRomSelect')) wbLoadRomPackages();
})();