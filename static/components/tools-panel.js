/**
 * ============================================================
 * 天树刷机 (Skytree Flasher) — <tools-panel> 工具箱组件
 * 
 * 功能：重启、VBmeta、AB槽位切换、双清、Bootloader 管理
 * 隔离性：Shadow DOM (closed)，完全自包含
 * ============================================================
 */

class ToolsPanel extends HTMLElement {
  static get observedAttributes() {
    return ['backend-url'];
  }

  constructor() {
    super();
    this._shadow = this.attachShadow({ mode: 'closed' });
    this._state = {
      backendUrl: this.getAttribute('backend-url') || '',
      blStatus: '未知',
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
        .section-title {
          font-size: 13px; font-weight: 600;
          margin: 16px 0 8px 0;
          color: var(--text-secondary, #8e8e93);
        }
        .card {
          background: var(--card-bg, #1c1c1e);
          border-radius: 12px;
          padding: 12px;
          margin-bottom: 10px;
        }
        .card-title {
          font-size: 13px; font-weight: 600; margin: 0 0 8px 0;
        }
        .btn-row {
          display: flex; gap: 6px; flex-wrap: wrap;
        }
        .btn {
          padding: 6px 14px; border: none; border-radius: 8px;
          font-size: 12px; cursor: pointer;
          background: var(--accent-blue, #0a84ff); color: #fff;
        }
        .btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .btn-secondary { background: var(--bg-tertiary, #2c2c2e); color: var(--text-primary, #fff); }
        .btn-secondary:hover { opacity: 0.8; }
        .btn-warn { background: var(--accent-orange, #ff9f0a); color: #fff; }
        .btn-danger { background: var(--accent-red, #ff453a); color: #fff; }

        .selector-row {
          display: flex; gap: 6px; align-items: center; margin: 6px 0; flex-wrap: wrap;
        }
        .selector-row select {
          padding: 5px 8px;
          background: var(--input-bg, #1c1c1e);
          border: 1px solid var(--input-border, #38383a);
          border-radius: 6px;
          color: var(--text-primary, #fff);
          font-size: 11px;
        }
        .status-text {
          font-size: 12px; color: var(--text-muted, #636366);
          margin: 4px 0;
        }
        .help-toggle {
          font-size: 11px; color: var(--accent-blue); cursor: pointer;
          margin-left: 4px;
        }

        .group-separator {
          margin: 8px 0; padding-top: 8px;
          border-top: 1px solid var(--separator, #38383a);
        }
      </style>

      <div class="section-title">🔧 工具箱</div>

      <!-- 重启操作 -->
      <div class="card">
        <div class="card-title">重启设备</div>
        <div class="btn-row">
          <button class="btn btn-secondary" data-cmd="reboot system">重启到系统</button>
          <button class="btn btn-secondary" data-cmd="reboot bootloader">重启到 Bootloader</button>
          <button class="btn btn-secondary" data-cmd="reboot fastboot">重启到 Fastbootd</button>
          <button class="btn btn-secondary" data-cmd="reboot recovery">重启到 Recovery</button>
        </div>
      </div>

      <!-- 高级操作 -->
      <div class="card">
        <div class="card-title" style="display:flex;align-items:center;gap:4px">
          ⚠️ 高级操作
          <span class="help-toggle" id="toggleAdv">展开 ▾</span>
        </div>
        <div id="advancedSection" style="display:none">

          <!-- VBmeta -->
          <div class="group-separator">
            <div class="card-title" style="font-size:12px">关闭 VBmeta 校验</div>
            <div class="selector-row">
              <select id="vbmetaSourceSelect">
                <option value="device">手机目录镜像</option>
                <option value="rom">已解压刷机包</option>
              </select>
              <select id="vbmetaSelect"><option value="">选择 vbmeta 镜像</option></select>
            </div>
            <div class="btn-row" style="margin-top:6px">
              <button class="btn btn-secondary" id="vbmetaBtn" disabled>执行关闭校验</button>
            </div>
            <div class="status-text">可从本地/刷机包选择镜像；设备连接后自动检测 vbmeta 校验状态。</div>
          </div>

          <!-- AB 槽位 -->
          <div class="group-separator">
            <div class="card-title" style="font-size:12px">AB 槽位切换</div>
            <div class="status-text">当前槽位：<span id="currentSlotText">未知</span></div>
            <div class="selector-row">
              <select id="targetSlotSelect">
                <option value="a">A 槽</option>
                <option value="b">B 槽</option>
              </select>
              <button class="btn btn-secondary" id="switchSlotBtn" disabled>立即切换</button>
            </div>
          </div>

          <!-- 双清 -->
          <div class="group-separator">
            <div class="card-title" style="font-size:12px">双清操作</div>
            <div class="btn-row">
              <button class="btn btn-warn" id="wipeBtn">执行双清</button>
              <button class="btn btn-secondary" id="eraseMetaBtn">擦除 metadata</button>
            </div>
          </div>

          <!-- Bootloader -->
          <div class="group-separator">
            <div class="card-title" style="font-size:12px">Bootloader 管理</div>
            <div class="status-text">Bootloader 锁状态：<span id="blStatus">未知</span></div>
            <div class="btn-row" style="margin-top:6px">
              <button class="btn btn-secondary" id="queryBlBtn">查询锁状态</button>
              <button class="btn btn-danger" id="unlockBlBtn">解锁 Bootloader</button>
              <button class="btn btn-danger" id="lockBlBtn">上锁 Bootloader</button>
            </div>
          </div>

        </div>
      </div>
    `;

    this._el = {
      toggleAdv: this._shadow.getElementById('toggleAdv'),
      advancedSection: this._shadow.getElementById('advancedSection'),
      vbmetaBtn: this._shadow.getElementById('vbmetaBtn'),
      switchSlotBtn: this._shadow.getElementById('switchSlotBtn'),
      wipeBtn: this._shadow.getElementById('wipeBtn'),
      eraseMetaBtn: this._shadow.getElementById('eraseMetaBtn'),
      queryBlBtn: this._shadow.getElementById('queryBlBtn'),
      unlockBlBtn: this._shadow.getElementById('unlockBlBtn'),
      lockBlBtn: this._shadow.getElementById('lockBlBtn'),
      currentSlotText: this._shadow.getElementById('currentSlotText'),
      blStatus: this._shadow.getElementById('blStatus'),
      targetSlotSelect: this._shadow.getElementById('targetSlotSelect'),
    };
  }

  _bindEvents() {
    const el = this._el;

    // 展开/收起高级操作
    el.toggleAdv.addEventListener('click', () => {
      const isOpen = el.advancedSection.style.display !== 'none';
      el.advancedSection.style.display = isOpen ? 'none' : 'block';
      el.toggleAdv.textContent = isOpen ? '展开 ▾' : '收起 ▴';
    });

    // 重启按钮（事件委托）
    this._shadow.querySelectorAll('[data-cmd]').forEach(btn => {
      btn.addEventListener('click', () => this._execReboot(btn.dataset.cmd));
    });

    // Bootloader
    el.queryBlBtn.addEventListener('click', () => this._queryBl());
    el.unlockBlBtn.addEventListener('click', () => this._execBl('unlock'));
    el.lockBlBtn.addEventListener('click', () => this._execBl('lock'));

    // 双清
    el.wipeBtn.addEventListener('click', () => this._execWipe());
    el.eraseMetaBtn.addEventListener('click', () => this._execCmd('fastboot', ['erase', 'metadata']));

    // AB 槽位
    el.switchSlotBtn.addEventListener('click', () => this._switchSlot());
  }

  // ============================================================
  // 命令执行
  // ============================================================

  async _api(path, body = {}) {
    const url = this._state.backendUrl || window.location.origin;
    const res = await fetch(`${url}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return await res.json();
  }

  async _execReboot(target) {
    const cmd = target.replace('reboot ', '');
    try {
      await this._api('/api/fastboot/exec', { args: ['reboot', cmd] });
    } catch (e) {
      console.warn('重启命令失败:', e);
    }
  }

  async _execCmd(tool, args) {
    const path = tool === 'fastboot' ? '/api/fastboot/exec' : '/api/adb/exec';
    try {
      return await this._api(path, { args });
    } catch (e) {
      console.warn(`命令失败 (${tool} ${args.join(' ')}):`, e);
    }
  }

  async _queryBl() {
    try {
      const data = await this._api('/api/fastboot/exec', { args: ['getvar', 'unlocked'] });
      const status = data.output && data.output.includes('yes') ? '已解锁' : '已锁定';
      this._el.blStatus.textContent = status;
    } catch (e) {
      this._el.blStatus.textContent = '查询失败';
    }
  }

  async _execBl(action) {
    if (!confirm(`确认${action === 'unlock' ? '解锁' : '上锁'} Bootloader？此操作可能清除所有数据！`)) return;
    await this._execCmd('fastboot', ['flashing', action]);
  }

  async _execWipe() {
    if (!confirm('确认执行双清？将清除 userdata 和 cache！')) return;
    await this._execCmd('fastboot', ['erase', 'userdata']);
    await this._execCmd('fastboot', ['erase', 'cache']);
  }

  async _switchSlot() {
    const target = this._el.targetSlotSelect.value;
    await this._execCmd('fastboot', ['set_active', target]);
  }
}

customElements.define('tools-panel', ToolsPanel);
console.log('[Component] <tools-panel> 已注册');
