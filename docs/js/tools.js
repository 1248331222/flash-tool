// flash_tool/static/js/tools.js
// ============ 版本与更新 ============
async function loadVersion() {
    const verEl = document.getElementById('versionToolVersion');
    if (!verEl) return;
    try {
        const d = await apiGet('/api/version');
        verEl.textContent = 'v' + d.version;
        // 渲染可折叠更新日志（版本页）
        renderChangelog('versionChangelog', d.version);
    } catch(e) {
        verEl.textContent = 'v?';
    }
}

async function checkUpdate(silent) {
    const tip = document.getElementById('versionUpdateTip');
    const btn = document.getElementById('versionUpdateBtn');
    if (!silent) {
        if (tip) tip.textContent = '正在检查更新...';
        if (btn) btn.disabled = true;
    }
    try {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), silent ? 5000 : 8000);
        const d = await parseApiResponse(await fetch((App.backendUrl || '') + '/api/update/check', {signal: ctrl.signal}), '/api/update/check');
        clearTimeout(timer);
        if (!d.success) {
            if (silent) return;
            throw new Error(d.error || '检查失败');
        }
        if (d.has_update) {
            if (tip) tip.innerHTML = `发现新版本 v${escHtml(d.remote_version)}（当前 v${escHtml(d.local_version)}）`;
            const doBtn = document.getElementById('versionDoUpdateBtn');
            if (doBtn) { doBtn.style.display = ''; doBtn.disabled = false; }
        } else {
            if (!silent && tip) tip.textContent = `已是最新版本 v${d.local_version}`;
        }
    } catch(e) {
        if (silent) return;
        if (e.name === 'AbortError') {
            if (tip) tip.textContent = '检查更新超时：网络较慢或服务器无响应';
        } else {
            if (tip) tip.textContent = '检查更新失败：' + e.message;
        }
    }
    if (!silent && btn) btn.disabled = false;
}

async function doUpdate() {
    const tip = document.getElementById('versionUpdateTip');
    const doBtn = document.getElementById('versionDoUpdateBtn');
    showConfirm('确认更新', '确认更新？更新后需要重启服务才能生效。', async () => {
        if (tip) tip.textContent = '正在下载更新...';
        if (doBtn) doBtn.disabled = true;
        try {
            const d = await apiPost('/api/update/do', {});
            if (!d.success) throw new Error(d.error || '更新失败');
            if (tip) tip.textContent = '更新成功！请停止并重新启动刷机工具以生效。';
            if (doBtn) doBtn.style.display = 'none';
        } catch(e) {
            if (tip) tip.textContent = '更新失败：' + e.message;
            if (doBtn) doBtn.disabled = false;
        }
    });
}

// ============ VBmeta（工具页：镜像加载与关闭校验） ============
document.getElementById('vbmetaSource').onchange = async () => {
    document.getElementById('vbmetaSelect').value = '';
    updateBtnState();
    if (document.getElementById('vbmetaSource').value === 'rom') {
        document.getElementById('vbmetaRomRow').style.display = 'flex';
        await loadVbmetaRomImages();
    } else {
        document.getElementById('vbmetaRomRow').style.display = 'none';
        await loadProjectImages();
    }
    updateBtnState();
};

async function loadVbmetaRomList() {
    try {
        const d = await apiGet('/api/rom/list');
        fillSelect(document.getElementById('vbmetaRomSelect'), d.dirs, '选择刷机包');
    } catch(e) {}
}

document.getElementById('vbmetaRomSelect').onchange = async () => {
    document.getElementById('vbmetaSelect').innerHTML = '<option value="">选择vbmeta镜像</option>';
    updateBtnState();
    await loadVbmetaRomImages();
    updateBtnState();
};

document.getElementById('vbmetaSelect').onchange = () => {
    updateBtnState();
};

async function loadVbmetaRomImages() {
    const rn = document.getElementById('vbmetaRomSelect').value;
    if (!rn) {
        document.getElementById('vbmetaSelect').innerHTML = '<option value="">选择vbmeta镜像</option>';
        updateBtnState();
        return;
    }
    try {
        const d = await apiGet(`/api/rom/images?rom_name=${encodeURIComponent(rn)}`);
        if (d.success) {
            fillSelect(document.getElementById('vbmetaSelect'), d.files, '选择vbmeta镜像');
            writeLog(`加载包内镜像：${d.files.length} 个`, 'info');
            updateBtnState();
        }
    } catch(e) { writeLog('加载失败：' + e.message, 'err'); }
    updateBtnState();
}

// ============ 关闭VBmeta校验 ============
document.getElementById('disableVbmetaBtn').onclick = () => {
    const img = document.getElementById('vbmetaSelect').value;
    const source = document.getElementById('vbmetaSource').value;
    const romName = document.getElementById('vbmetaRomSelect').value;
    if (!img) return;

    showConfirm('操作确认', '刷入 vbmeta 并关闭校验（--disable-verity --disable-verification），确认继续？', async () => {
        setModuleStatus('toolbox', '工具箱状态：准备刷入 vbmeta 并关闭校验。', 'warn');
        showModuleProgress('toolbox', '准备刷入 vbmeta');
        const reqData = {
            extra: '--disable-verity --disable-verification',
            source: source,
            image: img
        };
        if (source === 'rom') reqData.rom_name = romName;
        if (appRunMode === 'webusb') {
            if (!webusbFastbootReady || !webusbFastboot) {
                setModuleStatus('toolbox', 'WebUSB Fastboot 未连接，无法刷写 vbmeta。', 'err');
                return;
            }
            try {
                writeLog('WebUSB模式：刷入 vbmeta 并关闭 verity/verification。', 'tip');
                const bytes = await fetchImageBytes(source, img, romName);
                await webusbFastboot.flash('vbmeta', bytes, p => updateModuleProgress('toolbox', p, 'WebUSB刷写 vbmeta'));
                updateModuleProgress('toolbox', 100, 'vbmeta 已刷入');
                setModuleStatus('toolbox', 'WebUSB已刷入 vbmeta，校验关闭完成。', 'ok');
                showToast('WebUSB vbmeta 关闭校验完成');
            } catch(e) {
                hideModuleProgress('toolbox');
                setModuleStatus('toolbox', 'WebUSB vbmeta刷写失败：' + e.message, 'err');
            }
            return;
        }

        showProgress('刷写 vbmeta');
        setModuleStatus('toolbox', '工具箱状态：正在刷写分区 vbmeta。', 'info');
        writeLog('刷写 vbmeta...');

        const res = await apiPost('/api/flash', {...reqData, partition: 'vbmeta'});
        if (!res.success) {
            hideProgress();
            hideModuleProgress('toolbox');
            setModuleStatus('toolbox', `工具箱状态：vbmeta 启动刷写失败：${res.error}`, 'err');
            writeLog('vbmeta 刷写失败：' + res.error, 'err');
            return;
        }

        await new Promise(resolve => {
            pollTaskFallback(res.task_id, (ok, err) => {
                hideProgress();
                if (ok) {
                    updateModuleProgress('toolbox', 100, 'vbmeta 已刷入');
                    setModuleStatus('toolbox', '工具箱状态：已刷入 vbmeta，校验关闭完成。', 'ok');
                    writeLog('VBmeta校验关闭完成', 'ok');
                    if ('vibrate' in navigator) navigator.vibrate([200, 100, 200]);
                    showToast('关闭校验完成');
                } else {
                    hideModuleProgress('toolbox');
                    setModuleStatus('toolbox', `工具箱状态：vbmeta 刷写失败：${err}`, 'err');
                    writeLog('vbmeta 刷写失败：' + err, 'err');
                    showToast('关闭校验失败：' + err);
                }
                resolve();
            }, {module: 'toolbox', progressPrefix: '正在刷写 vbmeta'});
        });
    }, false);
};