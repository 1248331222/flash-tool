// flash_tool/static/js/config.js
// ============ 后端地址配置 ============
// 部署到 GitHub Pages 时，在这里配置你的后端服务器地址
// 局域网示例：http://192.168.1.100:5000
// 本机运行（默认）：留空即使用当前页面域名

(function() {
    // 尝试从 localStorage 读取用户保存的后端地址
    let savedUrl;
    try {
        savedUrl = localStorage.getItem('backend_api_url');
    } catch(e) {
        savedUrl = null;
    }

    // 默认后端地址：自动检测当前页面域名（适合本机 Flask 部署时走代理）
    // GitHub Pages 部署时此值为 https://1248331222.github.io，不是后端 → getWebdavBase() 会走直连
    const DEFAULT_BACKEND_URL = (function() {
        const origin = window.location.origin;
        if (origin.includes('github.io')) return '';
        return origin;
    })();

    App.backendUrl = savedUrl || DEFAULT_BACKEND_URL;

    // 保存后端地址到 localStorage（用户可在页面修改）
    window.saveBackendUrl = function(url) {
        url = url.trim().replace(/\/+$/, '');
        App.backendUrl = url;
        try {
            localStorage.setItem('backend_api_url', url);
        } catch(e) {}
        if (App.socket && App.socket.connected) {
            App.socket.disconnect();
        }
        if (typeof initWebSocket === 'function') {
            initWebSocket();
        }
        writeLog('后端地址已切换为：' + (url || '当前页面'), 'ok');
    };
})();