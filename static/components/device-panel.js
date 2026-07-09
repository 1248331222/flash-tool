/**
 * ============================================================
 * 天树刷机 — <device-panel> 设备连接组件
 * Shadow DOM (closed)，使用原版 UI 和完整功能
 * ============================================================
 */
class DevicePanel extends HTMLElement {
  static get observedAttributes() { return ['backend-url']; }

  constructor() {
    super();
    this._root = this.attachShadow({ mode: 'closed' });
    this._state = {
      backendUrl: '', appRunMode: 'backend', socket: null,
      deviceConnected: false, deviceMode: 'none',
      canAdb: false, canFastboot: false, currentSlot: '',
      isAbDevice: false, deviceInfo: {},
      webusbAdb: null, webusbAdbReady: false,
      webusbFastboot: null, webusbFastbootReady: false,
    };
    // 加载保存的状态
    try { this._state.appRunMode = localStorage.getItem('run_mode') || 'backend'; } catch(e) {}
    try { this._state.backendUrl = localStorage.getItem('backend_api_url') || ''; } catch(e) {}

    this._render();
    this._bindEvents();
  }

  connectedCallback() {
    // 监听全局事件
    this._unsubs = [
      Bus.on('backend:changed', d => { this._state.backendUrl = d.url; this._doUpdateEnvStatus(); }),
      Bus.on('ws:connected', () => { this._state.realtimeConnected = true; this._doUpdateEnvStatus(); }),
      Bus.on('ws:disconnected', () => { this._state.realtimeConnected = false; this._doUpdateEnvStatus(); }),
    ];
    // 初始化 WebUSB
    if (this._state.appRunMode === 'webusb') this._initWebUSB();
  }

  disconnectedCallback() { if (this._unsubs) this._unsubs.forEach(fn => fn()); }

  // ============================================================
  // 渲染（原版 HTML + CSS）
  // ============================================================
  _render() {
    this._root.innerHTML = `
<style>
/* ============ 原版 main.css 核心样式 ============ */
:host { display: block; font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; color: var(--text-primary,#fff); }
* { box-sizing: border-box; }
h3 { font-size: 15px; margin: 0 0 10px 0; }
h4 { font-size: 13px; margin: 6px 0; }
p { margin: 4px 0; }
a { color: var(--accent-blue); }

/* 模式切换头 */
.run-mode-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.run-mode-head h3 { margin: 0; }
.mode-more { font-size: 11px; color: var(--accent-blue); cursor: pointer; }

.run-mode-tabs { display: flex; gap: 0; background: var(--bg-tertiary,#2c2c2e); border-radius: 10px; padding: 3px; flex:1; }
.run-mode-tab { flex:1; padding: 7px 0; text-align: center; font-size: 12px; border: none; border-radius: 8px; cursor: pointer; background: transparent; color: var(--text-secondary,#8e8e93); transition: all .2s; font-family:inherit; }
.run-mode-tab.active { background: var(--accent-blue,#0a84ff); color: #fff; }

.mode-device-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
.device-connect-row { display: flex; gap: 4px; align-items: center; flex:1; flex-wrap: wrap; }

select { padding: 6px 8px; background: var(--input-bg,#1c1c1e); border:1px solid var(--input-border,#38383a); border-radius: 8px; color: var(--text-primary,#fff); font-size: 12px; }
select:focus { outline: 2px solid var(--accent-blue); outline-offset: -2px; }

.btn { padding: 6px 14px; border: none; border-radius: 8px; font-size: 12px; cursor: pointer; background: var(--accent-blue,#0a84ff); color: #fff; white-space: nowrap; font-family:inherit; }
.btn:disabled { opacity:0.4; cursor:not-allowed; }
.btn.small { padding: 5px 10px; font-size: 11px; }
.btn.secondary { background: var(--bg-tertiary,#2c2c2e); color: var(--text-primary,#fff); }
.btn.secondary:hover:not(:disabled) { opacity:0.8; }

.slot-badge { background: var(--bg-tertiary,#2c2c2e); padding: 4px 8px; border-radius: 6px; font-size: 11px; color: var(--text-secondary,#8e8e93); display:inline-block; }

.module-status { font-size: 12px; padding: 6px 0; color: var(--text-muted,#636366); }
.mode-status-compact { font-size: 11px; }
.tip { font-size: 11px; color: var(--text-muted,#636366); line-height:1.5; margin:4px 0; }

/* 智能卡 */
.smart-card { background: rgba(10,132,255,0.08); border:1px solid rgba(10,132,255,0.2); border-radius: 10px; padding: 12px; margin:8px 0; font-size:12px; }
.smart-card h4 { margin:0 0 4px 0; color:var(--accent-blue); }
.smart-actions { display:flex; gap:6px; margin-top:6px; }

/* 模式详情 */
.run-mode-detail { display:none; margin:8px 0; }
.run-mode-detail.open { display:block; }
.run-mode-grid { display:grid; gap:8px; }
.run-mode-card { background: var(--card-bg,#1c1c1e); border-radius: 10px; padding: 12px; font-size:12px; line-height:1.6; }
.run-mode-card h4 { margin:0 0 4px 0; }
.mode-check { display:inline-block; background:rgba(48,209,88,0.12); color:var(--accent-green,#30d158); padding:2px 8px; border-radius:4px; font-size:11px; margin-top:4px; }

/* 日志 */
.sub-section { margin-top:10px; }
.log-box { background:#000; border-radius:8px; padding:8px; max-height:120px; overflow-y:auto; font-family:var(--font-mono,'Consolas',monospace); font-size:11px; line-height:1.5; color:var(--accent-green); margin:4px 0; }
.log-box::-webkit-scrollbar { width:3px; }
.log-box::-webkit-scrollbar-thumb { background:var(--separator,#38383a); border-radius:2px; }
.log-line { word-break:break-all; }
.log-line.ok { color:var(--accent-green); }
.log-line.err { color:var(--accent-red); }
.log-line.warn { color:var(--accent-orange); }
.log-line.info { color:var(--accent-blue); }

.row { display:flex; gap:6px; align-items:center; margin:6px 0; flex-wrap:wrap; }

/* 进度条 */
.progress-container { display:none; align-items:center; gap:8px; margin:8px 0; padding:8px; background:var(--card-bg,#1c1c1e); border-radius:8px; }
.progress-container.show { display:flex; }
.progress-label { font-size:11px; color:var(--text-muted); white-space:nowrap; }
.progress-bar { flex:1; height:6px; background:var(--bg-tertiary,#2c2c2e); border-radius:3px; overflow:hidden; }
.progress-bar-fill { height:100%; background:var(--accent-blue); border-radius:3px; transition:width .3s; width:0%; }
.progress-text { font-size:11px; color:var(--text-muted); min-width:30px; text-align:right; }

/* 上传对话框 */
.upload-modal { position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.5); z-index:1000; display:none; align-items:center; justify-content:center; }
.upload-modal.open { display:flex; }
.upload-panel { background:var(--card-bg,#1c1c1e); border-radius:14px; padding:20px; max-width:400px; width:90%; }
.upload-panel h3 { margin:0 0 10px 0; }
</style>

<!-- 设备连接 -->
<div class="run-mode-head">
  <h3>设备连接</h3>
  <span class="mode-more" id="modeMoreBtn">模式说明 ▾</span>
</div>

<div class="mode-device-row">
  <div class="run-mode-tabs">
    <button class="run-mode-tab" data-mode="backend">后端模式</button>
    <button class="run-mode-tab" data-mode="webusb">WebUSB模式</button>
  </div>
</div>

<div class="device-connect-row">
  <select id="deviceSelect" style="flex:1;min-width:150px"><option value="">未选择设备</option></select>
  <button class="btn small" id="checkDeviceBtn">检测设备</button>
  <span id="slotBadge" class="slot-badge" style="display:none">当前槽位：-</span>
  <button class="btn secondary small" id="querySlotBtn" disabled>查询槽位</button>
</div>

<div class="module-status mode-status-compact" id="modeStatus">当前模式：后端模式</div>
<p class="tip" id="envTip">点击「检测设备」检测并选择设备；如手机弹出 USB 调试 / OTG / Termux:API 等授权窗口，请点击「允许」。</p>
<div class="module-status mode-status-compact" id="envDeviceStatus">设备状态：尚未检测设备。</div>

<!-- 智能卡 -->
<div class="smart-card" id="smartNextCard" style="display:none">
  <h4 id="smartNextTitle">下一步：连接设备</h4>
  <p id="smartNextText">请选择连接模式，然后点击"检测ADB/Fastboot设备"。</p>
  <div class="smart-actions">
    <button class="btn small" id="smartDetectBtn">检测设备</button>
  </div>
</div>

<!-- 模式说明 -->
<div class="run-mode-detail" id="modeDetail">
  <div class="run-mode-grid">
    <div class="run-mode-card">
      <h4>后端模式</h4>
      <p>依赖 Termux 后端、内置 fastboot 和系统 adb。支持刷机包解压、线刷、单分区刷写、VBmeta、Bootloader、槽位等完整功能。</p>
      <p>当前模式提示：设备检测、ADB/Fastboot 命令和刷写由 Termux 后端执行，适合完整刷机。</p>
      <span class="mode-check">推荐刷机使用</span>
    </div>
    <div class="run-mode-card">
      <h4>WebUSB模式</h4>
      <p>浏览器直接连接 ADB 或 Fastboot USB 接口，不依赖 Termux 的 adb/fastboot 检测。支持开机 ADB 命令，也支持 Bootloader 下的 WebUSB Fastboot 命令与镜像刷写。</p>
      <p>当前模式提示：ADB/Fastboot 命令优先由浏览器 WebUSB 直连执行；线刷/单分区刷写会使用 WebUSB Fastboot。</p>
      <span class="mode-check">适合浏览器直连</span>
    </div>
  </div>
</div>

<!-- 日志 -->
<div class="sub-section">
  <h3 style="font-size:13px;font-weight:600">📜 运行日志</h3>
  <div class="log-box" id="logBox"></div>
  <div class="row" style="justify-content:space-between">
    <button class="btn secondary small" id="clearLogBtn">清空日志</button>
    <button class="btn secondary small" id="exportLogBtn">导出日志</button>
  </div>
</div>

<!-- 后端地址 -->
<div class="row" style="margin-top:6px;gap:4px;align-items:center">
  <span style="font-size:11px;color:var(--text-muted);white-space:nowrap">后端地址</span>
  <input type="text" id="backendUrlInput" placeholder="留空=本机，例如 http://192.168.1.100:5000" style="flex:1;min-width:0;font-size:11px;padding:4px 6px;border:1px solid var(--input-border,#38383a);border-radius:6px;background:var(--input-bg,#1c1c1e);color:var(--text-primary,#fff)">
  <button class="btn secondary small" id="applyBackendUrlBtn" style="white-space:nowrap;font-size:11px">应用</button>
</div>

<!-- 进度条 -->
<div class="progress-container" id="progressContainer">
  <span class="progress-label" id="progressLabel">任务进度</span>
  <div class="progress-bar"><div class="progress-bar-fill" id="progressBarFill"></div></div>
  <span class="progress-text" id="progressText">0%</span>
</div>

<!-- 上传脚本对话框 -->
<div class="upload-modal" id="uploadModal">
  <div class="upload-panel">
    <h3>📤 上传脚本样本</h3>
    <p class="tip">选择刷机脚本文件上传到服务器，帮助改进天树解析引擎。</p>
    <input type="file" id="uploadFileInput" accept=".bat,.cmd,.sh,.txt" style="margin:8px 0;font-size:12px">
    <div class="row" style="margin-top:10px">
      <button class="btn small" id="uploadConfirmBtn">确认上传</button>
      <button class="btn secondary small" id="uploadCancelBtn">取消</button>
    </div>
    <div id="uploadStatus" class="tip" style="margin-top:6px"></div>
  </div>
</div>
`;
    this._el = {
      modeTabs: this._root.querySelectorAll('.run-mode-tab'),
      modeMore: this._root.getElementById('modeMoreBtn'),
      modeDetail: this._root.getElementById('modeDetail'),
      deviceSelect: this._root.getElementById('deviceSelect'),
      checkDeviceBtn: this._root.getElementById('checkDeviceBtn'),
      slotBadge: this._root.getElementById('slotBadge'),
      querySlotBtn: this._root.getElementById('querySlotBtn'),
      modeStatus: this._root.getElementById('modeStatus'),
      envTip: this._root.getElementById('envTip'),
      envDeviceStatus: this._root.getElementById('envDeviceStatus'),
      smartCard: this._root.getElementById('smartNextCard'),
      smartTitle: this._root.getElementById('smartNextTitle'),
      smartText: this._root.getElementById('smartNextText'),
      smartDetectBtn: this._root.getElementById('smartDetectBtn'),
      logBox: this._root.getElementById('logBox'),
      clearLogBtn: this._root.getElementById('clearLogBtn'),
      exportLogBtn: this._root.getElementById('exportLogBtn'),
      backendInput: this._root.getElementById('backendUrlInput'),
      applyBackendBtn: this._root.getElementById('applyBackendUrlBtn'),
      progressContainer: this._root.getElementById('progressContainer'),
      progressLabel: this._root.getElementById('progressLabel'),
      progressFill: this._root.getElementById('progressBarFill'),
      progressText: this._root.getElementById('progressText'),
      uploadModal: this._root.getElementById('uploadModal'),
      uploadInput: this._root.getElementById('uploadFileInput'),
      uploadConfirm: this._root.getElementById('uploadConfirmBtn'),
      uploadCancel: this._root.getElementById('uploadCancelBtn'),
      uploadStatus: this._root.getElementById('uploadStatus'),
    };
    // 恢复后端地址
    if (this._state.backendUrl) this._el.backendInput.value = this._state.backendUrl;
    // 初始模式
    this._setMode(this._state.appRunMode);
  }

  _bindEvents() {
    const el = this._el;

    // 模式切换
    el.modeTabs.forEach(t => t.addEventListener('click', () => this._setMode(t.dataset.mode)));
    el.modeMore.addEventListener('click', () => el.modeDetail.classList.toggle('open'));

    // 设备检测
    el.checkDeviceBtn.addEventListener('click', () => this._checkDevice());
    el.smartDetectBtn.addEventListener('click', () => this._checkDevice());

    // 槽位查询
    el.querySlotBtn.addEventListener('click', () => this._querySlot());

    // 日志
    el.clearLogBtn.addEventListener('click', () => el.logBox.innerHTML = '');
    el.exportLogBtn.addEventListener('click', () => this._exportLog());

    // 后端地址
    el.applyBackendBtn.addEventListener('click', () => this._applyBackend());
    el.backendInput.addEventListener('keydown', e => { if (e.key === 'Enter') this._applyBackend(); });

    // 上传
    el.uploadCancel.addEventListener('click', () => el.uploadModal.classList.remove('open'));
    el.uploadConfirm.addEventListener('click', () => this._doUpload());
  }

  // ============================================================
  // 业务逻辑
  // ============================================================

  _setMode(mode) {
    this._state.appRunMode = mode;
    this._el.modeTabs.forEach(t => t.classList.toggle('active', t.dataset.mode === mode));
    try { localStorage.setItem('run_mode', mode); } catch(e) {}
    this._el.modeStatus.textContent = `当前模式：${mode === 'backend' ? '后端模式' : 'WebUSB 模式'}`;
    this._el.envTip.textContent = mode === 'backend'
      ? '点击「检测设备」检测并选择设备；如手机弹出 USB 调试 / OTG / Termux:API 等授权窗口，请点击「允许」。'
      : 'WebUSB 模式下，使用浏览器直接连接设备 USB 接口。';
    if (mode === 'webusb') this._initWebUSB();
    Bus.emit('device:modeChanged', { mode });
  }

  /** 环境状态更新 */
  _doUpdateEnvStatus() {
    // 兼容旧 API 调用
  }

  async _initWebUSB() {
    if (!navigator.usb) { this._writeLog('⚠️ 浏览器不支持 WebUSB，请使用 Chrome/Edge', 'warn'); return; }
    this._writeLog('WebUSB 模式已启用', 'info');
    // 加载 WebUSB 库
    if (!window.WebUSB) {
      try {
        const mod = await import('/static/js/webusb.js');
        this._state.webusb = mod;
        this._writeLog('WebUSB 库加载完成', 'ok');
      } catch(e) {
        this._writeLog('WebUSB 库加载失败: ' + e.message, 'err');
      }
    }
  }

  async _checkDevice() {
    const btn = this._el.checkDeviceBtn;
    btn.disabled = true; btn.textContent = '检测中...';
    try {
      const url = this._state.backendUrl || window.location.origin;
      const res = await fetch(url + '/api/device/check', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        const devices = data.devices || [];
        this._el.deviceSelect.innerHTML = '<option value="">未选择设备</option>'
          + devices.map(d => `<option value="${d.serial||d.id||d}">${d.product||'设备'} (${d.serial||d.id||d})</option>`).join('');
        this._writeLog(`检测到 ${devices.length} 个设备`, 'ok');
        if (devices.length > 0) {
          this._el.envDeviceStatus.textContent = `设备状态：已连接设备`;
          this._el.smartCard.style.display = 'none';
          Bus.emit('device:connected', { device: devices[0] });
          App.setStatus('设备已连接', 'success');
          // 尝试获取详细信息
          this._fetchDeviceInfo(devices[0].serial || devices[0].id || devices[0]);
        }
      } else {
        this._writeLog(data.error || '检测失败', 'err');
        this._el.smartCard.style.display = '';
        this._el.smartTitle.textContent = '⚠️ 未检测到设备';
        this._el.smartText.textContent = '请确认手机已通过 USB 连接到服务器，并已开启 USB 调试。';
      }
    } catch(e) {
      this._writeLog('后端连接失败: ' + e.message, 'err');
      this._el.smartCard.style.display = '';
      this._el.smartTitle.textContent = '⚠️ 无法连接后端';
      this._el.smartText.textContent = this._state.backendUrl
        ? `请检查后端服务是否在 ${this._state.backendUrl} 运行`
        : '请先设置后端地址';
    } finally {
      btn.disabled = false; btn.textContent = '检测设备';
    }
  }

  async _fetchDeviceInfo(serial) {
    try {
      const url = this._state.backendUrl || window.location.origin;
      const res = await fetch(url + '/api/device/info', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ serial })
      });
      const data = await res.json();
      if (data.success) {
        this._state.deviceInfo = data.info || {};
        // 更新槽位信息
        if (data.info.slot) {
          this._state.currentSlot = data.info.slot;
          this._state.isAbDevice = true;
          this._el.slotBadge.style.display = '';
          this._el.slotBadge.textContent = `当前槽位：${data.info.slot}`;
          this._el.querySlotBtn.disabled = false;
        }
        Bus.emit('device:info', { info: data.info });
      }
    } catch(e) { /* 静默 */ }
  }

  async _querySlot() {
    try {
      const url = this._state.backendUrl || window.location.origin;
      const res = await fetch(url + '/api/fastboot/exec', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ args: ['getvar', 'current-slot'] })
      });
      const data = await res.json();
      if (data.output) {
        const slot = data.output.trim().split(/\s+/).pop();
        this._el.slotBadge.textContent = `当前槽位：${slot}`;
        this._writeLog(`当前槽位: ${slot}`, 'info');
      }
    } catch(e) {
      this._writeLog('查询槽位失败: ' + e.message, 'err');
    }
  }

  /** 应用后端地址 */
  _applyBackend() {
    const url = this._el.backendInput.value.trim();
    this._state.backendUrl = url;
    try { localStorage.setItem('backend_api_url', url); } catch(e) {}
    Bus.emit('backend:changed', { url });
    this._writeLog(`后端地址已切换为：${url || '(当前页面)'}`, 'ok');
  }

  /** 写日志 */
  _writeLog(msg, type = 'normal') {
    const box = this._el.logBox;
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    box.appendChild(line);
    box.scrollTop = box.scrollHeight;
  }

  /** 导出日志 */
  _exportLog() {
    const text = this._el.logBox.textContent;
    const b = new Blob([text], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(b);
    a.download = `device_log_${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(b);
  }

  /** 显示进度 */
  showProgress(label) {
    const el = this._el;
    el.progressContainer.classList.add('show');
    el.progressLabel.textContent = label || '任务进度';
    el.progressFill.style.width = '0%';
    el.progressText.textContent = '0%';
  }

  updateProgress(percent, msg) {
    const el = this._el;
    el.progressFill.style.width = percent + '%';
    el.progressText.textContent = percent + '%';
    if (msg) el.progressLabel.textContent = msg.substring(0, 30);
  }

  hideProgress() {
    this._el.progressContainer.classList.remove('show');
  }

  /** 上传脚本 */
  _doUpload() {
    const file = this._el.uploadInput.files[0];
    if (!file) { this._el.uploadStatus.textContent = '请选择文件'; return; }
    // 上传逻辑
    this._el.uploadStatus.textContent = '上传中...';
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const url = this._state.backendUrl || window.location.origin;
        const res = await fetch(url + '/api/upload/script', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: file.name, content: reader.result })
        });
        const data = await res.json();
        this._el.uploadStatus.textContent = data.success ? '上传成功，感谢贡献！' : '上传失败: ' + (data.error || '');
        if (data.success) setTimeout(() => this._el.uploadModal.classList.remove('open'), 1500);
      } catch(e) {
        this._el.uploadStatus.textContent = '上传失败: ' + e.message;
      }
    };
    reader.readAsText(file);
  }
}

customElements.define('device-panel', DevicePanel);
console.log('[Component] <device-panel> 已注册');
