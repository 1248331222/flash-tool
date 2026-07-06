/**
 * ============================================================
 * 天树刷机 — <version-panel> 版本信息组件（原版 UI）
 * ============================================================
 */
class VersionPanel extends HTMLElement {
  constructor() {
    super();
    this._root = this.attachShadow({ mode: 'closed' });
    this._state = { version: '...', updateUrl: '', backendUrl: '' };
    try { this._state.backendUrl = localStorage.getItem('backend_api_url') || ''; } catch(e) {}
    this._render();
  }
  connectedCallback() { this._fetchVersion(); this._renderChangelog(); this._unsub = Bus.on('backend:changed', d => { this._state.backendUrl = d.url; }); }
  disconnectedCallback() { if (this._unsub) this._unsub(); }

  _render() {
    this._root.innerHTML = `
<style>
:host { display:block; font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; color: var(--text-primary,#fff); }
h3 { font-size:15px; margin:0 0 10px 0; }
.btn { padding:6px 14px; border:none; border-radius:8px; font-size:12px; cursor:pointer; background:var(--accent-blue,#0a84ff); color:#fff; font-family:inherit; }
.btn.small { padding:5px 10px; font-size:11px; }
.btn.secondary { background:var(--bg-tertiary,#2c2c2e); color:var(--text-primary,#fff); }
.btn.secondary:hover { opacity:0.8; }
.btn:disabled { opacity:0.4; cursor:not-allowed; }

.version-head { display:flex; align-items:center; gap:8px; margin-bottom:10px; }
.version-card { background:var(--card-bg,#1c1c1e); border-radius:12px; padding:16px; box-shadow:var(--card-shadow,0 2px 12px rgba(0,0,0,0.3)); }
.version-row { display:flex; justify-content:space-between; align-items:center; padding:8px 0; }
.version-row + .version-row { border-top:1px solid var(--separator,#38383a); }
.version-label { color:var(--text-secondary,#8e8e93); font-size:13px; }
.version-number { font-size:16px; font-weight:700; color:var(--accent-blue,#0a84ff); }

.sub-section { margin-top:12px; }
.sub-section h3 { font-size:13px; color:var(--text-secondary); }
.version-changelog { background:var(--card-bg,#1c1c1e); border-radius:12px; padding:16px; max-height:400px; overflow-y:auto; font-size:12px; line-height:1.6; }
.version-changelog::-webkit-scrollbar { width:4px; }
.version-changelog::-webkit-scrollbar-thumb { background:var(--separator,#38383a); border-radius:2px; }

.tip { font-size:12px; color:var(--text-muted,#636366); margin-top:4px; }
.tip.success { color:var(--accent-green,#30d158); }
.tip.error { color:var(--accent-red,#ff453a); }
</style>

<div class="version-head"><h3>📋 版本信息</h3></div>
<div class="version-card">
  <div class="version-row">
    <span class="version-label">当前版本</span>
    <span class="version-number" id="verNum">...</span>
  </div>
  <div class="version-row">
    <button class="btn secondary small" id="checkBtn">检查更新</button>
    <button class="btn small" id="updateBtn" style="display:none">立即更新</button>
  </div>
  <div id="updateTip" class="tip"></div>
</div>

<div class="sub-section">
  <h3>📜 更新日志</h3>
  <div class="version-changelog" id="changelog"><div style="color:var(--text-muted)">加载中...</div></div>
</div>
`;
    this._el = {
      verNum: this._root.getElementById('verNum'),
      checkBtn: this._root.getElementById('checkBtn'),
      updateBtn: this._root.getElementById('updateBtn'),
      updateTip: this._root.getElementById('updateTip'),
      changelog: this._root.getElementById('changelog'),
    };
    this._el.checkBtn.addEventListener('click', () => this._checkUpdate());
    this._el.updateBtn.addEventListener('click', () => this._doUpdate());
  }

  async _fetchVersion() {
    try {
      const url = this._state.backendUrl || window.location.origin;
      const r = await fetch(url + '/api/version');
      const d = await r.json();
      if (d.success) { this._state.version = d.version; this._el.verNum.textContent = d.version; }
    } catch(e) { this._el.verNum.textContent = '获取失败'; this._el.verNum.style.color = 'var(--accent-red)'; }
  }

  async _checkUpdate() {
    const btn = this._el.checkBtn; btn.disabled = true; btn.textContent = '检查中...';
    try {
      const url = this._state.backendUrl || window.location.origin;
      const r = await fetch(url + '/api/update/check');
      const d = await r.json();
      if (d.hasUpdate) { this._el.updateTip.textContent = `新版本 ${d.latestVersion} 可用！`; this._el.updateTip.className = 'tip success'; this._el.updateBtn.style.display = ''; }
      else { this._el.updateTip.textContent = '已是最新版本'; this._el.updateTip.className = 'tip'; this._el.updateBtn.style.display = 'none'; }
    } catch(e) { this._el.updateTip.textContent = '检查失败: ' + e.message; this._el.updateTip.className = 'tip error'; }
    finally { btn.disabled = false; btn.textContent = '检查更新'; }
  }

  async _doUpdate() {
    const btn = this._el.updateBtn; btn.disabled = true; btn.textContent = '更新中...';
    try {
      const url = this._state.backendUrl || window.location.origin;
      const r = await fetch(url + '/api/update/do', { method: 'POST' });
      const d = await r.json();
      this._el.updateTip.textContent = d.success ? '更新完成，请刷新页面' : '更新失败: ' + (d.error || '');
      this._el.updateTip.className = d.success ? 'tip success' : 'tip error';
    } catch(e) { this._el.updateTip.textContent = '更新失败: ' + e.message; this._el.updateTip.className = 'tip error'; }
    finally { btn.disabled = false; btn.textContent = '立即更新'; }
  }

  _renderChangelog() {
    const logs = [
      { ver: 'v3.8.5', date: '2026-07-06', items: ['前端架构重构：Web Component 隔离', '上传脚本优化', 'UI 细节调整'] },
      { ver: 'v3.7.0', date: '2026-07-04', items: ['FTB 纯前端脚本视图修复', 'WebUSB 模式增强'] },
      { ver: 'v3.6.0', date: '2026-07-01', items: ['新增 SH 解析管线', 'BAT 解析引擎优化'] },
      { ver: 'v3.5.0', date: '2026-06-28', items: ['新增 WebUSB 刷机支持', '重构前端架构'] },
    ];
    this._fetchChangelog(logs);
  }

  async _fetchChangelog(fb) {
    try {
      const url = this._state.backendUrl || window.location.origin;
      const r = await fetch(url + '/api/changelog');
      const d = await r.json();
      if (d.success && d.changelog) { this._renderLogs(d.changelog); return; }
    } catch(e) { /* 降级 */ }
    this._renderLogs(fb);
  }

  _renderLogs(logs) {
    this._el.changelog.innerHTML = logs.map(l => `
      <div style="margin-bottom:12px">
        <strong style="color:var(--accent-blue);font-size:13px">${l.ver || l.version || ''}</strong>
        <span style="color:var(--text-muted);font-size:11px;margin-left:6px">${l.date || ''}</span>
        <ul style="margin:4px 0 0 0;padding-left:18px">
          ${(l.items || []).map(i => `<li style="margin:2px 0">${i}</li>`).join('')}
        </ul>
      </div>
    `).join('');
  }
}
customElements.define('version-panel', VersionPanel);
console.log('[Component] <version-panel> 已注册');
