// flash_tool/static/js/utils.js
// ============ 通用辅助函数 ============

/** HTML 转义，防止注入 */
function escHtml(s) {
    if (!s) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

/** 填充下拉选择框 */
function fillSelect(sel, list, def) {
    if (!sel) return;
    const cur = sel.value;
    sel.innerHTML = `<option value="">${def}</option>`;
    list.forEach(f => {
        const o = document.createElement('option');
        const val = (typeof f === 'object' && f !== null) ? (f.name || f.path || f.value || JSON.stringify(f)) : f;
        o.value = val;
        o.textContent = val;
        sel.appendChild(o);
    });
    const vals = list.map(f => (typeof f === 'object' && f !== null) ? (f.name || f.path || f.value) : f);
    if (vals.includes(cur)) sel.value = cur;
    updateBtnState();
}

/** 根据当前槽位格式化分区名（AB 设备自动补 _a/_b） */
function formatPartition(name) {
    if (!isAbDevice || !currentSlot) return name;
    if (/_[ab]$/i.test(name)) return name;
    return `${name}_${currentSlot}`;
}

/** 切换应用主视图 */
function switchAppView(view) {
    document.querySelectorAll('.app-view').forEach(el => {
        el.classList.toggle('active', el.dataset.view === view);
    });
    document.querySelectorAll('.nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.view === view);
    });
    localStorage.setItem('active_view', view);
    ensurePageLogBoxes();
    window.scrollTo({top: 0, behavior: 'smooth'});
    if (view === 'version' && typeof loadVersion === 'function') {
        loadVersion();
    }
}

/** Promise 版延时 */
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

/** 格式化命令执行结果，合并 logs/message/output/error/diagnosis */
function formatCommandResult(res) {
    const parts = [];
    if (res.logs && res.logs.length) parts.push(res.logs.join('\n'));
    if (res.message) parts.push(res.message);
    if (res.output) parts.push(String(res.output).trim());
    if (res.error) parts.push(String(res.error).trim());
    if (res.diagnosis) parts.push('诊断：' + res.diagnosis);
    return parts.filter(Boolean).join('\n').trim();
}

/** 判断是否为查询 BL 锁状态的命令 */
function isBlQueryCommand(tool, args) {
    return tool === 'fastboot'
        && args.length >= 2
        && String(args[0]).toLowerCase() === 'getvar'
        && String(args[1]).toLowerCase() === 'unlocked';
}

// 注：window.onload = init 已移至 init.js（在 init 函数定义之后）
