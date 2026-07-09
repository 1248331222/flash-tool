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
              <input type="text" id="vbmetaSelect" placeholder="镜像绝对路径，如 /sdcard/123456/image/vbmeta.img" style="flex:1;min-width:120px">
              <button class="btn btn-secondary" id="vbmetaPickBtn" title="从手机目录选择镜像文件">📂 或选择镜像文件</button>
            </div>
            <div class="btn-row" style="margin-top:6px">
              <button class="btn btn-secondary" id="vbmetaBtn" disabled>执行关闭校验</button>
            </div>
            <div class="status-text">输入镜像绝对路径或点击「选择」从刷机包目录选取 vbmeta.img；设备连接后自动检测校验状态。</div>
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
      vbmetaSelect: this._shadow.getElementById('vbmetaSelect'),
      vbmetaPickBtn: this._shadow.getElementById('vbmetaPickBtn'),
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

    // VBmeta 输入变化 → 更新按钮状态
    if (el.vbmetaSelect) {
      el.vbmetaSelect.addEventListener('input', () => this._updateVbmetaBtn());
      el.vbmetaSelect.addEventListener('change', () => this._updateVbmetaBtn());
    }
    // VBmeta 文件选择
    if (el.vbmetaPickBtn) {
      el.vbmetaPickBtn.addEventListener('click', () => this._pickVbmetaImage());
    }
    // VBmeta 执行关闭校验
    if (el.vbmetaBtn) {
      el.vbmetaBtn.addEventListener('click', () => this._disableVbmeta());
    }
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

  // ============================================================
  // VBmeta: 更新按钮状态 / 选择文件 / 执行关闭校验
  // ============================================================

  _updateVbmetaBtn() {
    const input = this._el.vbmetaSelect;
    const btn = this._el.vbmetaBtn;
    if (!btn || !input) return;
    btn.disabled = !input.value.trim();
  }

  async _pickVbmetaImage() {
    try {
      const data = await this._api('GET', '/api/rom/projects');
      // /api/rom/projects 返回 {success, dirs: [{name, type, class_id}]}
      const dirs = data && data.dirs;
      if (!dirs || dirs.length === 0) {
        alert('没有已解压的刷机包项目，请先在线刷页解压线刷包。');
        return;
      }
      const projects = dirs.map(d => d.name);
      // 构建选择列表弹窗
      let msg = '选择刷机包项目以选取 vbmeta.img：\n';
      projects.forEach((p, i) => { msg += `${i + 1}. ${p}\n`; });
      const idx = prompt(msg + '\n请输入编号 (1~' + projects.length + ')：');
      if (!idx) return;
      const i = parseInt(idx, 10);
      if (isNaN(i) || i < 1 || i > projects.length) { alert('无效编号'); return; }
      const project = projects[i - 1];

      // 用 /api/rom/images?rom_name=xxx 获取镜像文件列表
      const baseUrl = this._state.backendUrl || window.location.origin;
      const imgRes = await fetch(`${baseUrl}/api/rom/images?rom_name=${encodeURIComponent(project)}`);
      const imgData = await imgRes.json();
      if (!imgData || !imgData.files) {
        alert('获取镜像列表失败');
        return;
      }
      const files = imgData.files;
      // 过滤出 vbmeta 相关的镜像
      const vbmetaFiles = files.filter(f => f.toLowerCase().includes('vbmeta'));
      if (vbmetaFiles.length === 0) {
        let fileMsg = '该项目下未找到 vbmeta 文件，请手动输入路径或选其他项目。\n';
        fileMsg += '可用镜像文件：\n' + files.map((f, j) => `${j + 1}. ${f}`).join('\n');
        alert(fileMsg);
        this._el.vbmetaSelect.value = `/sdcard/123456/${project}/images/vbmeta.img`;
      } else if (vbmetaFiles.length === 1) {
        this._el.vbmetaSelect.value = `/sdcard/123456/${project}/images/${vbmetaFiles[0]}`;
      } else {
        let selMsg = '找到多个 vbmeta 文件：\n';
        vbmetaFiles.forEach((f, j) => { selMsg += `${j + 1}. ${f}\n`; });
        const selIdx = prompt(selMsg + '\n请选择编号 (1~' + vbmetaFiles.length + ')：');
        if (!selIdx) return;
        const si = parseInt(selIdx, 10);
        if (isNaN(si) || si < 1 || si > vbmetaFiles.length) { alert('无效编号'); return; }
        this._el.vbmetaSelect.value = `/sdcard/123456/${project}/images/${vbmetaFiles[si - 1]}`;
      }
      this._updateVbmetaBtn();
    } catch (e) {
      console.warn('选择 VBmeta 镜像失败:', e);
      alert('获取刷机包列表失败: ' + e.message);
    }
  }

  async _disableVbmeta() {
    const img = this._el.vbmetaSelect.value.trim();
    if (!img) { alert('请先输入或选择 vbmeta 镜像路径'); return; }

    if (!confirm('刷入 vbmeta 并关闭校验（--disable-verity --disable-verification），确认继续？')) return;

    const url = this._state.backendUrl || window.location.origin;
    try {
      const res = await fetch(`${url}/api/flash`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          partition: 'vbmeta',
          extra: '--disable-verity --disable-verification',
          source: 'path',
          image: img
        }),
      });
      const data = await res.json();
      if (data.success) {
        alert('VBmeta 刷写成功，校验已关闭！');
      } else {
        alert('VBmeta 刷写失败: ' + (data.error || '未知错误'));
      }
    } catch (e) {
      console.warn('VBmeta 关闭校验失败:', e);
      alert('请求失败: ' + e.message);
    }
  }
}

customElements.define('tools-panel', ToolsPanel);
console.log('[Component] <tools-panel> 已注册');