/**
 * ============================================================
 * 天树刷机 (Skytree Flasher) — <flash-panel> 线刷组件
 * 
 * 功能：ROM 选择 → 解压 → 解析脚本 → 执行线刷
 * 隔离性：Shadow DOM (closed)，完全自包含
 * ============================================================
 */

class FlashPanel extends HTMLElement {
  static get observedAttributes() {
    return ['backend-url'];
  }

  constructor() {
    super();
    this._shadow = this.attachShadow({ mode: 'closed' });
    this._state = {
      backendUrl: this.getAttribute('backend-url') || '',
      roms: [],
      projects: [],
      scripts: [],
      steps: [],
      selectedRom: null,
      selectedProject: null,
      selectedScript: null,
      flashHistory: [],
    };
    this._render();
    this._bindEvents();
  }

  connectedCallback() {
    this._unsub = SkytreeBus.on('backend:changed', (d) => {
      this._state.backendUrl = d.url;
    });
  }

  disconnectedCallback() {
    if (this._unsub) this._unsub();
  }

  _render() {
    this._shadow.innerHTML = `
      <style>
        :host { display: block; }
        h3 { font-size: 15px; margin: 0 0 8px 0; }
        h4 { font-size: 13px; margin: 8px 0; }

        .btn {
          padding: 6px 14px; border: none; border-radius: 8px;
          font-size: 12px; cursor: pointer;
          background: var(--accent-blue, #0a84ff); color: #fff;
        }
        .btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .btn-secondary { background: var(--bg-tertiary, #2c2c2e); color: var(--text-primary, #fff); }
        .btn-warn { background: var(--accent-orange, #ff9f0a); color: #fff; }
        .btn-danger { background: var(--accent-red, #ff453a); color: #fff; }
        .btn-small { padding: 4px 10px; font-size: 11px; }

        .card {
          background: var(--card-bg, #1c1c1e);
          border-radius: 12px; padding: 12px;
          margin-bottom: 10px;
        }

        .row {
          display: flex; gap: 6px; align-items: center;
          margin: 6px 0; flex-wrap: wrap;
        }
        .row select {
          flex: 1; min-width: 120px;
          padding: 5px 8px;
          background: var(--input-bg, #1c1c1e);
          border: 1px solid var(--input-border, #38383a);
          border-radius: 6px;
          color: var(--text-primary, #fff);
          font-size: 11px;
        }

        .help-content {
          font-size: 12px; display: none;
          background: var(--bg-tertiary, #2c2c2e);
          border-radius: 8px; padding: 10px;
          margin: 6px 0;
        }
        .help-content.open { display: block; }
        .help-content ol { margin: 4px 0; padding-left: 20px; }
        .help-content li { margin: 3px 0; color: var(--text-secondary); }

        .help-toggle {
          font-size: 11px; color: var(--accent-blue); cursor: pointer;
        }

        .tip {
          font-size: 11px; color: var(--text-muted);
          margin: 4px 0;
        }

        .step-list {
          background: var(--card-bg, #1c1c1e);
          border-radius: 8px;
          max-height: 300px; overflow-y: auto;
          font-size: 12px;
        }
        .step-item {
          padding: 6px 10px;
          border-bottom: 1px solid var(--separator, #38383a);
        }
        .step-item:last-child { border-bottom: none; }

        .module-status {
          font-size: 12px; padding: 6px;
          color: var(--text-muted);
        }

        .history-item {
          padding: 6px 0;
          border-bottom: 1px solid var(--separator, #38383a);
          font-size: 11px;
        }

        .batch-output {
          background: #000; color: var(--accent-green);
          border-radius: 8px; padding: 10px;
          max-height: 200px; overflow-y: auto;
          font-family: var(--font-mono, monospace);
          font-size: 11px;
          margin-top: 8px;
          display: none;
        }

        .file-list {
          max-height: 200px; overflow-y: auto;
          font-size: 11px;
        }
        .file-item {
          padding: 4px 8px;
          border-bottom: 1px solid var(--separator);
        }
      </style>

      <h3>⇅ 线刷 <span class="help-toggle" id="helpToggle">使用说明 ▾</span></h3>

      <div class="help-content" id="helpContent">
        <ol>
          <li>线刷包放入手机 123456 文件夹</li>
          <li>刷新列表→选择→复制解压</li>
          <li>解析 BAT/CMD/SH 脚本即可执行线刷</li>
        </ol>
      </div>

      <!-- ROM 选择 -->
      <div class="card">
        <div class="row">
          <button class="btn btn-secondary btn-small" id="refreshRomBtn">刷新</button>
          <select id="romSelect"><option value="">选择线刷包</option></select>
          <button class="btn btn-small" id="extractBtn" disabled>解压</button>
        </div>
      </div>

      <!-- 项目/脚本 -->
      <div class="card">
        <div class="row">
          <button class="btn btn-secondary btn-small" id="refreshProjBtn">刷新项目</button>
          <select id="projSelect"><option value="">选择已解压线刷项目</option></select>
        </div>
        <div class="row">
          <button class="btn btn-secondary btn-small" id="refreshScriptBtn">刷新脚本</button>
          <select id="scriptSelect"><option value="">选择刷机脚本</option></select>
          <button class="btn btn-small" id="parseBtn" disabled>解析脚本</button>
        </div>
        <div class="tip" style="margin-top:4px">
          解析失败？<a href="#" id="uploadLink" style="color:var(--accent-orange)">📤 上传此脚本样本</a>
        </div>
      </div>

      <!-- 已解压列表 -->
      <div id="extractedList" class="file-list" style="display:none"></div>

      <!-- 步骤列表 -->
      <div id="stepList" class="step-list" style="display:none">
        <div style="padding:12px;text-align:center;color:var(--text-muted)">解析脚本生成步骤</div>
      </div>

      <!-- 执行栏 -->
      <div class="card" id="execBar" style="display:none">
        <div class="module-status" id="flashStatus">线刷状态：等待解析脚本并检测设备。</div>
        <div class="row">
          <button class="btn btn-warn" id="flashBtn" disabled>执行线刷</button>
          <button class="btn btn-secondary btn-small" id="simulateBtn" disabled>模拟刷入</button>
          <button class="btn btn-secondary btn-small" id="clearStepsBtn" disabled>清空步骤</button>
        </div>
      </div>

      <!-- 输出 -->
      <div class="batch-output" id="batchOutput"></div>

      <!-- 刷机历史 -->
      <div style="margin-top:12px">
        <div style="font-size:13px;font-weight:600;color:var(--text-secondary);margin-bottom:6px">📋 刷机历史</div>
        <button class="btn btn-secondary btn-small" id="loadHistoryBtn">加载历史记录</button>
        <div id="historyList" style="margin-top:6px"></div>
      </div>
    `;

    this._el = {
      helpToggle: this._shadow.getElementById('helpToggle'),
      helpContent: this._shadow.getElementById('helpContent'),
      refreshRomBtn: this._shadow.getElementById('refreshRomBtn'),
      romSelect: this._shadow.getElementById('romSelect'),
      extractBtn: this._shadow.getElementById('extractBtn'),
      refreshProjBtn: this._shadow.getElementById('refreshProjBtn'),
      projSelect: this._shadow.getElementById('projSelect'),
      refreshScriptBtn: this._shadow.getElementById('refreshScriptBtn'),
      scriptSelect: this._shadow.getElementById('scriptSelect'),
      parseBtn: this._shadow.getElementById('parseBtn'),
      uploadLink: this._shadow.getElementById('uploadLink'),
      extractedList: this._shadow.getElementById('extractedList'),
      stepList: this._shadow.getElementById('stepList'),
      execBar: this._shadow.getElementById('execBar'),
      flashStatus: this._shadow.getElementById('flashStatus'),
      flashBtn: this._shadow.getElementById('flashBtn'),
      simulateBtn: this._shadow.getElementById('simulateBtn'),
      clearStepsBtn: this._shadow.getElementById('clearStepsBtn'),
      batchOutput: this._shadow.getElementById('batchOutput'),
      loadHistoryBtn: this._shadow.getElementById('loadHistoryBtn'),
      historyList: this._shadow.getElementById('historyList'),
    };
  }

  _bindEvents() {
    const el = this._el;

    el.helpToggle.addEventListener('click', () => {
      el.helpContent.classList.toggle('open');
    });

    el.refreshRomBtn.addEventListener('click', () => this._refreshRoms());
    el.extractBtn.addEventListener('click', () => this._extractRom());
    el.refreshProjBtn.addEventListener('click', () => this._refreshProjects());
    el.refreshScriptBtn.addEventListener('click', () => this._refreshScripts());
    el.parseBtn.addEventListener('click', () => this._parseScript());
    el.flashBtn.addEventListener('click', () => this._executeFlash());
    el.simulateBtn.addEventListener('click', () => this._simulateFlash());
    el.clearStepsBtn.addEventListener('click', () => this._clearSteps());
    el.loadHistoryBtn.addEventListener('click', () => this._loadHistory());
    el.uploadLink.addEventListener('click', (e) => { e.preventDefault(); this._uploadScript(); });
  }

  // ============================================================
  // API 调用
  // ============================================================

  async _api(method, path, body) {
    const url = this._state.backendUrl || window.location.origin;
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${url}${path}`, opts);
    return await res.json();
  }

  async _refreshRoms() {
    try {
      const data = await this._api('GET', '/api/rom/list');
      if (data.success) {
        this._state.roms = data.roms || [];
        this._el.romSelect.innerHTML = '<option value="">选择线刷包</option>'
          + this._state.roms.map(r => `<option value="${r}">${r}</option>`).join('');
        this._el.extractBtn.disabled = false;
      }
    } catch (e) {
      console.warn('获取 ROM 列表失败:', e);
    }
  }

  async _extractRom() {
    const rom = this._el.romSelect.value;
    if (!rom) return;
    this._el.extractBtn.disabled = true;
    this._el.extractBtn.textContent = '解压中...';
    try {
      await this._api('POST', '/api/rom/extract', { name: rom });
      await this._refreshProjects();
    } catch (e) {
      console.warn('解压失败:', e);
    } finally {
      this._el.extractBtn.disabled = false;
      this._el.extractBtn.textContent = '解压';
    }
  }

  async _refreshProjects() {
    try {
      const data = await this._api('GET', '/api/rom/projects');
      if (data.success) {
        this._state.projects = data.projects || [];
        this._el.projSelect.innerHTML = '<option value="">选择已解压线刷项目</option>'
          + this._state.projects.map(p => `<option value="${p}">${p}</option>`).join('');
      }
    } catch (e) { /* ignore */ }
  }

  async _refreshScripts() {
    const proj = this._el.projSelect.value;
    if (!proj) return;
    try {
      const data = await this._api('GET', `/api/rom/scripts?project=${encodeURIComponent(proj)}`);
      if (data.success) {
        this._state.selectedProject = proj;
        this._el.scriptSelect.innerHTML = '<option value="">选择刷机脚本</option>'
          + data.scripts.map(s => `<option value="${s}">${s}</option>`).join('');
        this._el.parseBtn.disabled = false;
      }
    } catch (e) { /* ignore */ }
  }

  async _parseScript() {
    const script = this._el.scriptSelect.value;
    const proj = this._el.projSelect.value;
    if (!script || !proj) return;
    try {
      const data = await this._api('POST', '/api/rom/parse', { project: proj, script });
      if (data.success) {
        this._state.steps = data.steps || [];
        this._renderSteps();
        this._el.execBar.style.display = '';
        this._el.flashBtn.disabled = false;
        this._el.simulateBtn.disabled = false;
      }
    } catch (e) { /* ignore */ }
  }

  _renderSteps() {
    const el = this._el.stepList;
    el.style.display = '';
    if (this._state.steps.length === 0) {
      el.innerHTML = '<div style="padding:12px;text-align:center;color:var(--text-muted)">无步骤</div>';
      return;
    }
    el.innerHTML = this._state.steps.map((s, i) => `
      <div class="step-item">
        <strong>#${i + 1}</strong>
        <span style="color:var(--accent-orange)">${s.type || 'cmd'}</span>
        ${s.part ? `<span style="color:var(--accent-blue)">${s.part}</span>` : ''}
        <span style="color:var(--text-muted)">${s.fileName || s.params || s.command || ''}</span>
      </div>
    `).join('');
  }

  async _executeFlash() {
    if (this._state.steps.length === 0) return;
    this._el.flashBtn.disabled = true;
    this._el.flashBtn.textContent = '执行中...';
    this._el.batchOutput.style.display = '';
    this._el.batchOutput.innerHTML = '';
    try {
      const data = await this._api('POST', '/api/flash/exec', {
        project: this._el.projSelect.value,
        steps: this._state.steps,
      });
      if (data.output) {
        this._el.batchOutput.innerHTML = data.output.replace(/\n/g, '<br>');
      }
    } catch (e) {
      this._el.batchOutput.innerHTML = '执行失败: ' + e.message;
    } finally {
      this._el.flashBtn.disabled = false;
      this._el.flashBtn.textContent = '执行线刷';
    }
  }

  async _simulateFlash() {
    // 简单模拟
    alert('模拟刷入：步骤将通过 API 模拟执行，请确认设备已连接。');
  }

  _clearSteps() {
    this._state.steps = [];
    this._el.stepList.style.display = 'none';
    this._el.execBar.style.display = 'none';
  }

  _uploadScript() {
    alert('上传功能：请选择脚本文件上传到服务器帮助改进解析引擎。');
  }

  async _loadHistory() {
    try {
      const data = await this._api('GET', '/api/history');
      if (data.success && data.history) {
        this._el.historyList.innerHTML = data.history.map(h => `
          <div class="history-item">${h.time || ''} - ${h.rom || h.script || '线刷'} ${h.success ? '✅' : '❌'}</div>
        `).join('');
      }
    } catch (e) { /* ignore */ }
  }
}

customElements.define('flash-panel', FlashPanel);
console.log('[Component] <flash-panel> 已注册');
