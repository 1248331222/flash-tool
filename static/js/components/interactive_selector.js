// flash_tool/static/js/interactive_selector.js
// ============ 交互式脚本【逐层+进度选择器】 ============
//
// 先将 pending_choices 树拍平成顺序抉择列表，然后逐条展示。
// 每条 只显示当前要选的选项，选中打勾→点下一步→下一条。
// 顶部显示 "抉择 x/N" 进度。
// ============================================================

Modules.register('interactive-selector', [], function initInteractiveSelectorModule() {
    'use strict';

    var _allChoices = {};
    var _onComplete = null;
    var _onCancel = null;
    var _selected = null;
    var _overlay = null;
    var _dialog = null;
    var _timer = null;

    // 顺序抉择列表
    var _steps = [];        // [{title, desc, options: [{value,label,desc,step_count}]}]
    var _currentIdx = 0;    // 当前展示到第几步

    // ==================== 拍平树为顺序步骤 ====================

    /**
     * 将 pending_choices 树拍平为顺序抉择列表
     * 只保留 needs_choice=true 的层级作为一步
     * needs_choice=false + auto_select 的层自动处理，不留步骤
     */
    function _flattenTree(choices, parentTitle) {
        if (!choices || choices.length === 0) return;

        // 检查是否是顺序抉择组（_sequential_group）
        if (choices.length > 0 && choices[0]._sequential_group) {
            // 顺序抉择：每个元素是一个步骤
            choices.forEach(function(group) {
                if (group._sequential_group && group.choices) {
                    var opts = group.choices.map(function(item) {
                        return {
                            value: item.value,
                            label: item.label || item.value,
                            description: item.description || '',
                            step_count: item.step_count || 0,
                            raw: item
                        };
                    });
                    _steps.push({
                        title: group._step_title || '请选择',
                        desc: group._step_desc || '',
                        options: opts
                    });
                }
            });
            return;
        }

        // 分出需要弹窗的和自动走的
        var needChoice = [];
        var autoItems = [];

        choices.forEach(function(item) {
            if (item.needs_choice === true) {
                needChoice.push(item);
            } else {
                autoItems.push(item);
            }
        });

        // 如果有需要弹窗的 → 加入步骤列表
        if (needChoice.length > 0) {
            var title = '';
            var desc = '';
            // 从needChoice中取标题
            if (needChoice[0]) {
                title = parentTitle || needChoice[0].label || needChoice[0].value || '请选择';
                desc = needChoice[0].description || '';
            }

            // 构建这一步的options（只展示需要选择的项）
            var opts = needChoice.map(function(item) {
                return {
                    value: item.value,
                    label: item.label || item.value,
                    description: item.description || '',
                    step_count: item.step_count,
                    raw: item
                };
            });

            _steps.push({
                title: title,
                desc: desc,
                options: opts
            });
        }

        // 处理 auto_items：自动走，并递归其子级
        autoItems.forEach(function(item) {
            _recordChoice(item.value);

            if (item.auto_select && item.auto_select.length > 0) {
                _recordChoice(item.auto_select);
                // 找 auto_select 对应的子项
                var matched = null;
                (item.children || []).forEach(function(c) {
                    if (c.value === item.auto_select) matched = c;
                });
                if (matched && matched.children && matched.children.length > 0) {
                    _flattenTree(matched.children, matched.label || matched.value);
                }
            } else if (item.children && item.children.length > 0) {
                _flattenTree(item.children, item.label || item.value);
            }
        });

        // 处理 needChoice 中每个选项的子级（递归展平）
        needChoice.forEach(function(item) {
            if (item.children && item.children.length > 0) {
                _flattenTree(item.children, item.label || item.value);
            }
        });
    }

    /**
     * 记录一个 value 到选择字典
     */
    function _recordChoice(value) {
        if (!value) return;
        var eqIdx = value.indexOf('=');
        if (eqIdx > 0) {
            var key = value.substring(0, eqIdx).trim();
            var val = value.substring(eqIdx + 1).trim();
            _allChoices[key] = val;
        }
    }

    // ==================== 展示当前步骤 ====================

    function _showStep() {
        if (_currentIdx >= _steps.length) {
            // 所有步骤展示完毕 → 完成
            _finish();
            return;
        }

        var step = _steps[_currentIdx];
        var isLast = (_currentIdx === _steps.length - 1);
        _selected = null;

        // 遮罩
        if (!_overlay) {
            _overlay = document.createElement('div');
            _overlay.className = 'modal-overlay';
            _overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:9999;display:flex;align-items:center;justify-content:center;';
            document.body.appendChild(_overlay);
        }

        // 对话框
        if (_dialog) { try { _overlay.removeChild(_dialog); } catch(e) {} }
        _dialog = document.createElement('div');
        _dialog.className = 'modal-dialog';
        _dialog.style.cssText = 'background:var(--bg-card,#1e1e2e);border-radius:12px;padding:20px;max-width:400px;width:90%;box-shadow:0 8px 32px rgba(0,0,0,0.4);display:flex;flex-direction:column;max-height:85vh;';

        // ---- 进度 ----
        var progressBar = document.createElement('div');
        progressBar.style.cssText = 'margin-bottom:10px;font-size:11px;color:var(--text-muted,#888);';
        progressBar.textContent = '抉择 ' + (_currentIdx + 1) + '/' + _steps.length;
        _dialog.appendChild(progressBar);

        // ---- 标题 ----
        var h = document.createElement('h3');
        h.textContent = step.title;
        h.style.cssText = 'margin:0 0 4px 0;font-size:16px;color:var(--text-primary,#e0e0e0);';
        _dialog.appendChild(h);

        // ---- 描述 ----
        if (step.desc) {
            var d = document.createElement('p');
            d.textContent = step.desc;
            d.style.cssText = 'margin:0 0 14px 0;font-size:13px;color:var(--text-muted,#999);line-height:1.4;';
            _dialog.appendChild(d);
        }

        // ---- 选项区（可滚动） ----
        var optArea = document.createElement('div');
        optArea.style.cssText = 'flex:1;overflow-y:auto;min-height:0;';

        step.options.forEach(function(opt) {
            var item = document.createElement('div');
            item.className = 'interactive-option';
            item.style.cssText = 'display:flex;align-items:center;padding:10px 12px;margin-bottom:6px;border:1px solid var(--border-color,#333);border-radius:8px;background:var(--bg-input,#2a2a3e);cursor:pointer;transition:all 0.15s;';

            // 圆圈勾选
            var circle = document.createElement('span');
            circle.style.cssText = 'width:20px;height:20px;border-radius:50%;border:2px solid var(--text-muted,#555);display:flex;align-items:center;justify-content:center;margin-right:10px;flex-shrink:0;font-size:12px;color:transparent;transition:all 0.15s;';
            circle.textContent = '✓';
            item.appendChild(circle);

            // 文本区
            var txt = document.createElement('div');
            txt.style.cssText = 'flex:1;min-width:0;';

            var label = document.createElement('div');
            label.style.cssText = 'font-weight:500;color:var(--accent-green,#4CAF50);font-size:13px;';
            label.textContent = opt.label;
            txt.appendChild(label);

            if (opt.description) {
                var desc2 = document.createElement('div');
                desc2.style.cssText = 'font-size:11px;color:var(--text-muted,#999);margin-top:2px;';
                desc2.textContent = opt.description;
                txt.appendChild(desc2);
            }
            if (opt.step_count !== undefined && opt.step_count > 0) {
                var cnt = document.createElement('div');
                cnt.style.cssText = 'font-size:10px;color:var(--text-muted,#666);margin-top:2px;';
                cnt.textContent = '预估 ' + opt.step_count + ' 步';
                txt.appendChild(cnt);
            }
            item.appendChild(txt);

            // hover
            item.onmouseenter = function() {
                if (this.dataset.selected !== 'true') {
                    this.style.borderColor = 'var(--accent-green,#4CAF50)';
                    this.style.background = 'rgba(76,175,80,0.08)';
                }
            };
            item.onmouseleave = function() {
                if (this.dataset.selected !== 'true') {
                    this.style.borderColor = 'var(--border-color,#333)';
                    this.style.background = 'var(--bg-input,#2a2a3e)';
                }
            };

            // 点击选中
            item.onclick = function() {
                _dialog.querySelectorAll('.interactive-option').forEach(function(el) {
                    el.dataset.selected = 'false';
                    el.style.borderColor = 'var(--border-color,#333)';
                    el.style.background = 'var(--bg-input,#2a2a3e)';
                    var c = el.querySelector('span:first-child');
                    if (c) { c.style.borderColor = 'var(--text-muted,#555)'; c.style.color = 'transparent'; c.style.background = 'transparent'; }
                });
                this.dataset.selected = 'true';
                this.style.borderColor = 'var(--accent-green,#4CAF50)';
                this.style.background = 'rgba(76,175,80,0.15)';
                circle.style.borderColor = 'var(--accent-green,#4CAF50)';
                circle.style.color = '#fff';
                circle.style.background = 'var(--accent-green,#4CAF50)';
                _selected = opt;
            };

            optArea.appendChild(item);
        });

        _dialog.appendChild(optArea);

        // ---- 底部按钮（固定） ----
        var bottomRow = document.createElement('div');
        bottomRow.style.cssText = 'display:flex;gap:8px;margin-top:10px;flex-shrink:0;';

        var cancelBtn = document.createElement('button');
        cancelBtn.textContent = '取消';
        cancelBtn.style.cssText = 'padding:8px 14px;border:1px solid var(--border-color,#333);border-radius:8px;background:transparent;color:var(--text-muted,#999);font-size:12px;cursor:pointer;';
        cancelBtn.onmouseenter = function() { this.style.color = 'var(--text-primary,#e0e0e0)'; };
        cancelBtn.onmouseleave = function() { this.style.color = 'var(--text-muted,#999)'; };
        cancelBtn.onclick = function() { _doCancel(); };
        bottomRow.appendChild(cancelBtn);

        var nextBtn = document.createElement('button');
        nextBtn.textContent = isLast ? '确定' : '下一步';
        nextBtn.style.cssText = 'flex:1;padding:10px;border:none;border-radius:8px;background:var(--accent-green,#4CAF50);color:#fff;font-size:13px;font-weight:500;cursor:pointer;opacity:0.5;';
        nextBtn.disabled = true;

        if (_timer) clearInterval(_timer);
        _timer = setInterval(function() {
            if (_selected) {
                nextBtn.style.opacity = '1';
                nextBtn.disabled = false;
            } else {
                nextBtn.style.opacity = '0.5';
                nextBtn.disabled = true;
            }
        }, 200);

        nextBtn.onclick = function() {
            if (!_selected) return;
            if (_timer) clearInterval(_timer);
            _timer = null;

            // 记录选择
            _recordChoice(_selected.value);

            // 进入下一步
            _cleanupDialog();
            _currentIdx++;
            _showStep();
        };
        bottomRow.appendChild(nextBtn);

        _dialog.appendChild(bottomRow);
        _overlay.appendChild(_dialog);
    }

    function _finish() {
        _cleanup();
        if (_onComplete) _onComplete(_allChoices);
        _reset();
    }

    function _doCancel() {
        _cleanup();
        if (_onCancel) _onCancel();
        _reset();
    }

    function _cleanupDialog() {
        if (_timer) { clearInterval(_timer); _timer = null; }
        if (_dialog && _overlay) { try { _overlay.removeChild(_dialog); } catch(e) {} _dialog = null; }
    }

    function _cleanup() {
        if (_timer) { clearInterval(_timer); _timer = null; }
        if (_dialog && _overlay) { try { _overlay.removeChild(_dialog); } catch(e) {} _dialog = null; }
        if (_overlay) { try { document.body.removeChild(_overlay); } catch(e) {} _overlay = null; }
    }

    function _reset() {
        _allChoices = {};
        _onComplete = null;
        _onCancel = null;
        _selected = null;
        _steps = [];
        _currentIdx = 0;
        if (_timer) { clearInterval(_timer); _timer = null; }
        _overlay = null;
        _dialog = null;
    }

    // ==================== 公开 API ====================

    window.interactiveSelector = {
        show: function(choices, callbacks) {
            _reset();
            if (!choices || choices.length === 0) {
                if (callbacks && callbacks.onComplete) callbacks.onComplete({});
                return;
            }
            _onComplete = callbacks.onComplete || null;
            _onCancel = callbacks.onCancel || null;

            // 拍平树为顺序步骤
            _flattenTree(choices, '选择刷机模式');

            if (_steps.length === 0) {
                // 没有需要抉择的步骤，直接完成
                if (_onComplete) _onComplete(_allChoices);
                _reset();
                return;
            }

            // 从第一步开始展示
            _currentIdx = 0;
            _showStep();
        },
        destroy: function() { _reset(); }
    };

    console.log('[interactive-selector] 交互式选择器模块已初始化');
    return true;
});