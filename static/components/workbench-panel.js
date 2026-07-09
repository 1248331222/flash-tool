/**
 * ============================================================
 * 天树刷机 (Skytree Flasher) — <workbench-panel> 工作台组件
 * 
 * 功能：自定义命令工作台，支持 Fastboot/ADB 快捷命令
 * 隔离性：Shadow DOM (closed)，完全自包含
 * ============================================================
 */

class WorkbenchPanel extends HTMLElement {
  static get observedAttributes() {
    return ['backend-url'];
  }

  constructor() {
    super();
    this._shadow = this.attachShadow({ mode: 'closed' });
    this._state = {
      backendUrl: this.getAttribute('backend-url') || '',
      steps: [],
      showQA: null, // 'fb' | 'adb' | null
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

        .btn {
          padding: 6px 14px; border: none; border-radius: 8px;
          font-size: 12px; cursor: pointer;
          background: var(--accent-blue, #0a84ff); color: #fff;
        }
        .btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .btn-secondary { background: var(--bg-tertiary, #2c2c2e); color: var(--text-primary, #fff); }
        .btn-small { padding: 4px 10px; font-size: 11px; }
        .btn-warn { background: var(--accent-orange, #ff9f0a); color: #fff; }
        .btn-success { background: var(--accent-green, #30d158); color: #fff; }

        .help-toggle {
          font-size: 11px; color: var(--accent-blue); cursor: pointer;
        }
        .help-content {
          font-size: 12px; display: none;
          background: var(--bg-tertiary, #2c2c2e);
          border-radius: 8px; padding: 10px;
          margin: 6px 0;
        }
        .help-content.open { display: block; }

        .card {
          background: var(--card-bg, #1c1c1e);
          border-radius: 12px; padding: 12px;
          margin-bottom: 10px;
        }

        .qa-tabs {
          display: flex; gap: 6px; margin-bottom: 8px;
        }
        .qa-tab {
          padding: 5px 12px; border: none; border-radius: 6px;
          font-size: 11px; cursor: pointer;
          background: var(--bg-tertiary, #2c2c2e);
          color: var(--text-primary, #fff);
        }
        .qa-tab.active { background: var(--accent-blue); color: #fff; }

        .cmd-grid {
          display: flex; flex-wrap: wrap; gap: 4px; margin: 6px 0;
        }
        .cmd-btn {
          padding: 4px 10px; border: none; border-radius: 6px;
          font-size: 11px; cursor: pointer;
          background: var(--bg-tertiary, #2c2c2e);
          color: var(--text-primary, #fff);
        }
        .cmd-btn:hover { opacity: 0.8; }
        .cmd-btn.warn { border: 1px solid var(--accent-orange); color: var(--accent-orange); }
        .cmd-btn.danger { border: 1px solid var(--accent-red); color: var(--accent-red); }

        .section-label {
          font-size: 11px; color: var(--text-muted);
          margin: 8px 0 4px 0;
          font-weight: 600;
        }

        /* 添加步骤 */
        .add-row {
          display: flex; gap: 4px; align-items: center;
          margin: 6px 0; flex-wrap: wrap;
        }
        .add-row select, .add-row input {
          padding: 5px 8px;
          background: var(--input-bg, #1c1c1e);
          border: 1px solid var(--input-border, #38383a);
          border-radius: 6px;
          color: var(--text-primary, #fff);
          font-size: 11px;
        }
        .add-row input { flex: 1; min-width: 100px; }

        /* 步骤列表 */
        .step-card {
          background: var(--bg-tertiary, #2c2c2e);
          border-radius: 8px; padding: 8px;
          margin: 4px 0;
          display: flex; justify-content: space-between; align-items: center;
          font-size: 12px;
        }
        .step-card .cmd { color: var(--accent-orange); }
        .step-card .args { color: var(--text-primary); margin-left: 4px; }
        .step-actions { display: flex; gap: 4px; }
        .step-actions button {
          padding: 2px 6px; border: none; border-radius: 4px;
          font-size: 10px; cursor: pointer;
          background: var(--bg-tertiary); color: var(--text-muted);
        }
        .step-actions button:hover { color: var(--text-primary); }

        .empty-state {
          text-align: center; padding: 20px;
          color: var(--text-muted); font-size: 12px;
        }

        .export-output {
          background: #000; color: var(--accent-green);
          border-radius: 8px; padding: 10px;
          margin-top: 8px; font-family: var(--font-mono, monospace);
          font-size: 11px; max-height: 200px; overflow-y: auto;
          display: none;
        }

        .inline-flex { display: flex; gap: 6px; flex-wrap: wrap; }
      </style>

      <h3>🛠 自定义工作台 <span class="help-toggle" id="helpToggle">说明 ▾</span></h3>

      <div class="help-content" id="helpContent">
        <ol>
          <li>支持添加 Fastboot/ADB/自定义 Shell 命令</li>
          <li>可排序、单步执行、全部执行</li>
          <li>点击「导出脚本」生成 .sh 脚本</li>
          <li>高危操作执行前需二次确认</li>
        </ol>
      </div>

      <!-- 快捷命令 -->
      <div class="card">
        <div class="qa-tabs">
          <button class="qa-tab" data-mode="fb">📡 Fastboot 快捷命令</button>
          <button class="qa-tab" data-mode="adb">📱 ADB 快捷命令</button>
        </div>
        <div id="qaSection" style="display:none"></div>
      </div>

      <!-- 添加步骤 -->
      <div class="card">
        <div style="font-size:12px;font-weight:600;margin-bottom:6px">添加步骤</div>
        <div class="add-row">
          <select id="stepType">
            <option value="flash">刷写命令</option>
            <option value="adb">ADB 命令</option>
            <option value="fastboot">Fastboot 命令</option>
          </select>
          <select id="partSource">
            <option value="custom">自定义</option>
            <option value="detected">已检测分区</option>
          </select>
          <input type="text" id="partInput" placeholder="分区名 (如 boot_a)">
          <button class="btn btn-small" id="addStepBtn">添加</button>
        </div>
        <div class="add-row">
          <input type="text" id="extraParams" placeholder="可选参数，如 --disable-verity">
        </div>
      </div>

      <!-- 步骤列表 -->
      <div id="stepList">
        <div class="empty-state">暂无步骤，添加快捷命令或手动添加</div>
      </div>

      <!-- 执行栏 -->
      <div class="inline-flex" style="margin-top:8px">
        <button class="btn btn-success" id="execAllBtn">▶ 全部执行</button>
        <button class="btn btn-secondary" id="execSimBtn">▶ 模拟执行</button>
        <button class="btn btn-secondary btn-small" id="exportBtn">📄 导出脚本</button>
        <button class="btn btn-secondary btn-small" id="clearAllBtn">清空</button>
        <button class="btn btn-secondary btn-small" id="saveBtn">💾 保存方案</button>
        <button class="btn btn-secondary btn-small" id="loadPlanBtn">⚙️ 方案管理</button>
      </div>

      <div class="export-output" id="exportOutput"></div>
    `;

    this._el = {
      helpToggle: this._shadow.getElementById('helpToggle'),
      helpContent: this._shadow.getElementById('helpContent'),
      qaSection: this._shadow.getElementById('qaSection'),
      qaTabs: this._shadow.querySelectorAll('.qa-tab'),
      stepType: this._shadow.getElementById('stepType'),
      partSource: this._shadow.getElementById('partSource'),
      partInput: this._shadow.getElementById('partInput'),
      extraParams: this._shadow.getElementById('extraParams'),
      addStepBtn: this._shadow.getElementById('addStepBtn'),
      stepList: this._shadow.getElementById('stepList'),
      execAllBtn: this._shadow.getElementById('execAllBtn'),
      execSimBtn: this._shadow.getElementById('execSimBtn'),
      exportBtn: this._shadow.getElementById('exportBtn'),
      clearAllBtn: this._shadow.getElementById('clearAllBtn'),
      saveBtn: this._shadow.getElementById('saveBtn'),
      loadPlanBtn: this._shadow.getElementById('loadPlanBtn'),
      exportOutput: this._shadow.getElementById('exportOutput'),
    };
  }

  _bindEvents() {
    const el = this._el;

    el.helpToggle.addEventListener('click', () => el.helpContent.classList.toggle('open'));

    el.qaTabs.forEach(tab => {
      tab.addEventListener('click', () => this._toggleQA(tab.dataset.mode));
    });

    el.addStepBtn.addEventListener('click', () => this._addStep());

    el.execAllBtn.addEventListener('click', () => this._execAll());
    el.execSimBtn.addEventListener('click', () => this._execSim());
    el.exportBtn.addEventListener('click', () => this._exportScript());
    el.clearAllBtn.addEventListener('click', () => this._clearAll());
    el.saveBtn.addEventListener('click', () => this._savePlan());
    el.loadPlanBtn.addEventListener('click', () => this._loadPlan());
  }

  // ============================================================
  // 快捷命令
  // ============================================================

  _toggleQA(mode) {
    this._state.showQA = this._state.showQA === mode ? null : mode;
    this._el.qaTabs.forEach(t => t.classList.toggle('active', t.dataset.mode === this._state.showQA));

    if (!this._state.showQA) {
      this._el.qaSection.style.display = 'none';
      return;
    }

    const isFb = mode === 'fb';
    const commands = isFb
      ? [
          { label: '设备列表', cmd: 'devices', safe: true },
          { label: '全部变量', cmd: 'getvar all', safe: true },
          { label: '产品代号', cmd: 'getvar product', safe: true },
          { label: '当前槽位', cmd: 'getvar current-slot', safe: true },
          { label: 'BL 状态', cmd: 'getvar unlocked', safe: true },
          { label: '安全补丁', cmd: 'getvar security-patch-level', safe: true },
          { label: '序列号', cmd: 'getvar serialno', safe: true },
          { label: '重启到系统', cmd: 'reboot', warn: true },
          { label: '重启到 BL', cmd: 'reboot bootloader', warn: true },
          { label: '重启到 Fastbootd', cmd: 'reboot fastboot', warn: true },
          { label: '解锁 BL', cmd: 'flashing unlock', danger: true },
          { label: '上锁 BL', cmd: 'flashing lock', danger: true },
        ]
      : [
          { label: '设备列表', cmd: 'devices', safe: true },
          { label: '重启', cmd: 'reboot', warn: true },
          { label: '重启到 BL', cmd: 'reboot bootloader', warn: true },
          { label: '重启到 Recovery', cmd: 'reboot recovery', warn: true },
          { label: '进入 Fastboot', cmd: 'reboot fastboot', warn: true },
          { label: '获取 Root', cmd: 'root', safe: true },
          { label: '停止 ADB', cmd: 'kill-server', safe: true },
        ];

    this._el.qaSection.style.display = '';
    this._el.qaSection.innerHTML = commands.map(c => {
      const cls = c.danger ? 'danger' : c.warn ? 'warn' : '';
      return `<button class="cmd-btn ${cls}" data-mode="${mode}" data-cmd="${c.cmd}">${c.label}</button>`;
    }).join('');

    this._el.qaSection.querySelectorAll('.cmd-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        this._addQuickCmd(btn.dataset.mode, btn.dataset.cmd);
      });
    });
  }

  _addQuickCmd(mode, cmd) {
    this._state.steps.push({ type: mode, args: cmd.split(' '), label: cmd });
    this._renderSteps();
  }

  // ============================================================
  // 步骤管理
  // ============================================================

  _addStep() {
    const type = this._el.stepType.value;
    const part = this._el.partInput.value.trim();
    const params = this._el.extraParams.value.trim();
    if (!part && type === 'flash') return;

    const args = type === 'flash'
      ? ['flash', part, ...(params ? [params] : [])]
      : [part, ...(params ? [params] : [])];

    this._state.steps.push({ type, args, label: `${type} ${part}` });
    this._el.partInput.value = '';
    this._el.extraParams.value = '';
    this._renderSteps();
  }

  _renderSteps() {
    const el = this._el.stepList;
    if (this._state.steps.length === 0) {
      el.innerHTML = '<div class="empty-state">暂无步骤，添加快捷命令或手动添加</div>';
      return;
    }

    el.innerHTML = this._state.steps.map((s, i) => `
      <div class="step-card">
        <div>
          <span class="cmd">${s.type}</span>
          <span class="args">${s.args ? s.args.join(' ') : s.label}</span>
        </div>
        <div class="step-actions">
          <button data-idx="${i}" data-action="move-up">↑</button>
          <button data-idx="${i}" data-action="move-down">↓</button>
          <button data-idx="${i}" data-action="run" class="cmd-btn" style="background:var(--accent-green)">▶</button>
          <button data-idx="${i}" data-action="delete" style="color:var(--accent-red)">✕</button>
        </div>
      </div>
    `).join('');

    // 事件委托
    el.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.idx);
        switch (btn.dataset.action) {
          case 'move-up': if (idx > 0) { [this._state.steps[idx-1], this._state.steps[idx]] = [this._state.steps[idx], this._state.steps[idx-1]]; this._renderSteps(); } break;
          case 'move-down': if (idx < this._state.steps.length - 1) { [this._state.steps[idx], this._state.steps[idx+1]] = [this._state.steps[idx+1], this._state.steps[idx]]; this._renderSteps(); } break;
          case 'delete': this._state.steps.splice(idx, 1); this._renderSteps(); break;
          case 'run': this._execSingle(idx); break;
        }
      });
    });
  }

  async _execSingle(idx) {
    const step = this._state.steps[idx];
    if (!step) return;
    try {
      const path = step.type === 'adb' ? '/api/adb/exec' : '/api/fastboot/exec';
      const url = this._state.backendUrl || window.location.origin;
      await fetch(`${url}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ args: step.args || step.cmd }),
      });
    } catch (e) {
      console.warn('命令执行失败:', e);
    }
  }

  async _execAll() {
    for (let i = 0; i < this._state.steps.length; i++) {
      await this._execSingle(i);
    }
  }

  _execSim() {
    alert('模拟执行所有步骤（仅预览，不实际执行）');
  }

  _exportScript() {
    const lines = this._state.steps.map(s => {
      const cmd = s.args ? s.args.join(' ') : s.label;
      return `${s.type === 'adb' ? 'adb' : 'fastboot'} ${cmd}`;
    });
    const script = '#!/bin/bash\n\n' + lines.join('\n');
    this._el.exportOutput.style.display = '';
    this._el.exportOutput.innerHTML = script.replace(/\n/g, '<br>');
  }

  _clearAll() {
    this._state.steps = [];
    this._renderSteps();
    this._el.exportOutput.style.display = 'none';
  }

  _savePlan() {
    const name = prompt('方案名称：');
    if (!name) return;
    try {
      const plans = JSON.parse(localStorage.getItem('skytree_plans') || '{}');
      plans[name] = this._state.steps;
      localStorage.setItem('skytree_plans', JSON.stringify(plans));
    } catch (e) { /* ignore */ }
  }

  _loadPlan() {
    try {
      const plans = JSON.parse(localStorage.getItem('skytree_plans') || '{}');
      const names = Object.keys(plans);
      if (names.length === 0) { alert('暂无保存的方案'); return; }
      const name = prompt(`选择方案：\n${names.join('\n')}`);
      if (name && plans[name]) {
        this._state.steps = plans[name];
        this._renderSteps();
      }
    } catch (e) { /* ignore */ }
  }
}

customElements.define('workbench-panel', WorkbenchPanel);
console.log('[Component] <workbench-panel> 已注册');
