// flash_tool/static/js/init.js
// ============ 初始化 ============

async function init() {
    try {
        preventPullToRefresh();
        ensurePageLogBoxes();
        initWebSocket();
        setRunMode(appRunMode);

        // 底部导航事件委托
        document.querySelector('.bottom-nav').addEventListener('click', (e) => {
            const navItem = e.target.closest('.nav-item');
            if (!navItem) return;
            const view = navItem.dataset.view;
            if (view) switchAppView(view);
        });

        let _savedView;
        try { _savedView = localStorage.getItem('active_view'); } catch(e) { _savedView = null; }
        switchAppView(_savedView || 'device');
        await checkEnv();

        if (backendReady) {
            try {
                // 并行加载，加快初始化速度
                await Promise.all([
                    loadProjectImages(),
                    refreshRomList(),
                    refreshExtractedRoms(),
                    loadVbmetaRomList(),
                ]);
                updateResumeCard();
                restoreBackendBatchTaskIfRunning();
                // 后端模式下，自动恢复设备状态（无需用户手动点击检测设备）
                if (appRunMode === 'backend') {
                    document.getElementById('checkDeviceBtn').click();
                }
                // 启动时静默检查更新（离线/超时不影响使用）
                checkUpdate(true);
            } catch(e) {
                writeLog('初始化加载失败：' + e.message, 'err');
            }
        }
    } catch(e) {
        writeLog('页面初始化错误：' + e.message, 'err');
    }
    loadVersion();
}

// 阻止页面下拉刷新（移动端：仅在顶部下拉时阻止默认行为）
function preventPullToRefresh() {
    let startY = 0;
    let startX = 0;
    document.addEventListener('touchstart', e => {
        if (!e.touches || e.touches.length !== 1) return;
        startY = e.touches[0].clientY;
        startX = e.touches[0].clientX;
    }, {passive: true});
    document.addEventListener('touchmove', e => {
        if (!e.touches || e.touches.length !== 1) return;
        const dy = e.touches[0].clientY - startY;
        const dx = Math.abs(e.touches[0].clientX - startX);
        if (window.scrollY <= 0 && dy > 8 && dy > dx) {
            e.preventDefault();
        }
    }, {passive: false});
}

// 启动入口（放在最后，确保 init 函数已定义）
window.onload = function() {
    // 初始化后端地址输入框
    const urlInput = document.getElementById('backendUrlInput');
    const applyBtn = document.getElementById('applyBackendUrlBtn');
    if (urlInput && applyBtn) {
        // 显示当前保存的后端地址
        const currentUrl = App.backendUrl || '';
        urlInput.value = currentUrl;
        // 点击应用按钮
        applyBtn.onclick = function() {
            const newUrl = urlInput.value.trim();
            if (typeof saveBackendUrl === 'function') {
                saveBackendUrl(newUrl);
            }
        };
        // 按回车也触发
        urlInput.onkeydown = function(e) {
            if (e.key === 'Enter' && applyBtn) {
                applyBtn.click();
            }
        };
    }
    init();
};