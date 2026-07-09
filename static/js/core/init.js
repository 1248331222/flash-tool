// flash_tool/static/js/init.js
// ============ 应用初始化 ============
// 改造后：通过 Modules.register 注册初始化模块，DOMReady 后统一调用。
// 所有 DOM 查询使用 SafeDOM，避免解析期/运行时因元素缺失崩溃。

/**
 * 应用初始化入口模块。
 * 在 ui / api / device 等基础模块初始化完成后执行，负责绑定导航、恢复视图、
 * 加载初始数据、恢复后端任务、检查更新等启动流程；所有异常均捕获并记录到日志，避免单点失败导致页面白屏。
 */
Modules.register('app-init', ['ui', 'api', 'device'], async function initApp() {
    try {
        preventPullToRefresh();
        ensurePageLogBoxes();
        initWebSocket();
        setRunMode(appRunMode);

        // 底部导航事件委托
        const bottomNav = document.querySelector('.bottom-nav');
        if (bottomNav) {
            bottomNav.addEventListener('click', (e) => {
                const navItem = e.target.closest('.nav-item');
                if (!navItem) return;
                const view = navItem.dataset.view;
                if (view) switchAppView(view);
            });
        } else {
            console.warn('[app-init] 未找到底部导航 .bottom-nav');
        }

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
                    const checkBtn = $('checkDeviceBtn');
                    if (checkBtn && typeof checkBtn.click === 'function') {
                        checkBtn.click();
                    }
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
});

/**
 * 阻止移动端页面下拉刷新：仅在顶部垂直下拉时拦截默认行为，保留横向滚动体验。
 */
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

/**
 * 启动入口：DOMContentLoaded 后初始化后端地址输入框，再触发模块系统完成应用启动。
 * 模块系统初始化异常会在 catch 中输出到控制台，避免阻塞页面渲染。
 */
window.addEventListener('DOMContentLoaded', function() {
    // 初始化后端地址输入框
    const urlInput = $('backendUrlInput');
    const applyBtn = $('applyBackendUrlBtn');
    if (urlInput.value !== undefined && applyBtn.click !== undefined) {
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
            if (e.key === 'Enter' && applyBtn && typeof applyBtn.click === 'function') {
                applyBtn.click();
            }
        };
    }

    // 启动模块初始化系统
    Modules.init().then(() => {
        console.log('[init] 应用初始化完成');
    }).catch(err => {
        console.error('[init] 模块初始化异常:', err);
    });
});
