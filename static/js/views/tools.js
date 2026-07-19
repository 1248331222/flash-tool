// flash_tool/static/js/tools.js
// 版本/工具模块

/**
 * 从后端加载当前工具版本号，并触发版本日志渲染和全局状态更新。
 */
async function loadVersion() {
    const verEl = document.getElementById('versionToolVersion');
    if (!verEl) return;
    try {
        const d = await apiGet('/api/version');
        verEl.textContent = 'v' + d.version;
        if (typeof renderVersionChangelog === 'function') {
            renderVersionChangelog('versionChangelog', d.version);
        }
        if (App && typeof App.set === 'function') {
            App.set('toolVersion', d.version);
        }
    } catch(e) {
        verEl.textContent = 'v?';
    }
}

/**
 * 检查后端是否有新版本可用。
 */
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

// ============ VBmeta（文件管理器选择镜像 + 参数位置可选） ============

function getVbmetaImagePath() {
    const input = document.getElementById('vbmetaImagePath');
    return input ? input.value.trim() : '';
}

function updateVbmetaBtnState() {
    const btn = document.getElementById('disableVbmetaBtn');
    if (!btn) return;
    btn.disabled = !getVbmetaImagePath();
}

async function pickVbmetaImage() {
    try {
        const file = await FileApi.pickFile({ filter: '.img' });
        if (!file) return;
        const input = document.getElementById('vbmetaImagePath');
        const display = document.getElementById('vbmetaPathDisplay');
        if (input) input.value = file.path || '';
        if (display) display.textContent = '📄 ' + (file.name || file.path || '');
        updateVbmetaBtnState();
    } catch(e) {
        if (e.message !== '用户取消选择') {
            if (typeof showToast === 'function') showToast('选择文件失败: ' + e.message);
        }
    }
}

async function disableVbmeta() {
    const img = getVbmetaImagePath();
    if (!img) return;

    const paramPos = document.getElementById('vbmetaParamPos');
    const pos = paramPos ? paramPos.value : 'after';
    const disableFlags = '--disable-verity --disable-verification';

    const extraAfter = pos === 'after' ? disableFlags : '';
    const extraBefore = pos === 'before' ? disableFlags : '';

    const cmdDesc = pos === 'before'
        ? `fastboot ${disableFlags} flash vbmeta 镜像`
        : `fastboot flash vbmeta 镜像 ${disableFlags}`;

    showConfirm('操作确认', '刷入 vbmeta 并关闭校验（' + cmdDesc + '），确认继续？', async () => {
        setModuleStatus('toolbox', '工具箱状态：准备刷入 vbmeta 并关闭校验。', 'warn');
        showModuleProgress('toolbox', '准备刷入 vbmeta');
        const reqData = {
            extra: extraAfter,
            extra_before: extraBefore,
            source: 'path',
            image: img
        };
        if (appRunMode === 'webusb') {
            if (!webusbFastbootReady || !webusbFastboot) {
                setModuleStatus('toolbox', 'WebUSB Fastboot 未连接，无法刷写 vbmeta。', 'err');
                return;
            }
            try {
                writeLog('WebUSB模式：刷入 vbmeta 并关闭 verity/verification。', 'tip');
                const bytes = await fetchImageBytes('path', img);
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
}

// ============ 版本/工具模块事件委托 ============
function handleVersionAction(e) {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const action = btn.dataset.action;
    if (action === 'check-update') {
        e.preventDefault();
        checkUpdate(false);
    } else if (action === 'do-update') {
        e.preventDefault();
        doUpdate();
    }
}

// ============ 模块初始化 ============
Modules.register('tools', ['api','utils','device-info'], function initToolsModule() {
    // VBmeta 文件选择按钮
    const vbmetaPickBtn = document.getElementById('vbmetaPickBtn');
    if (vbmetaPickBtn) vbmetaPickBtn.onclick = pickVbmetaImage;

    // VBmeta 执行关闭校验
    const disableVbmetaBtn = document.getElementById('disableVbmetaBtn');
    if (disableVbmetaBtn) disableVbmetaBtn.onclick = disableVbmeta;

    loadVersion();

    console.log('[tools] 版本/工具模块已初始化');
    return true;
});