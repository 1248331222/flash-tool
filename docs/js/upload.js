// flash_tool/static/js/upload.js
// ============ 脚本上传功能 ============

let _selectedUploadFile = null;
// 上传成功后刷新列表
function refreshUploadList() {
    const listEl = document.getElementById('uploadHistoryList');
    if (!listEl) return;
    
    const baseUrl = window.BACKEND_API_URL || '';
    fetch(baseUrl + '/api/script/list')
        .then(r => r.json())
        .then(data => {
            if (!data.success || !data.files.length) {
                listEl.innerHTML = '<div style="text-align:center;padding:12px;color:var(--text-muted);font-size:12px">暂无上传记录</div>';
                return;
            }
            listEl.innerHTML = data.files.map(f => {
                const region = f.brand ? 
                    (f.brand === 'xiaomi' ? '广东网友' : 
                     f.brand === 'oneplus' ? '浙江网友' :
                     f.brand === 'samsung' ? '山东网友' :
                     f.brand === 'huawei' ? '北京网友' :
                     f.brand === 'oppo' ? '四川网友' :
                     f.brand === 'vivo' ? '湖北网友' :
                     `${f.brand}网友`) : '匿名网友';
                const time = f.upload_time ? f.upload_time.slice(5, 16) : '';
                return `<div class="upload-history-item">
                    <div class="upload-history-name">${escHtml(f.original_name)}</div>
                    <div class="upload-history-meta">
                        <span>${region}</span>
                        ${f.step_count ? `<span>${f.step_count}步</span>` : ''}
                        ${time ? `<span>${time}</span>` : ''}
                        <span class="upload-history-type">${f.script_type}</span>
                    </div>
                </div>`;
            }).join('');
        })
        .catch(() => {
            listEl.innerHTML = '<div style="text-align:center;padding:12px;color:var(--text-muted);font-size:12px">加载失败</div>';
        });
}

// 打开对话框时刷新列表
function openUploadDialog() {
    const dialog = document.getElementById('uploadDialog');
    if (dialog) dialog.classList.add('show');
    
    // 重置状态
    document.getElementById('uploadFileInput').value = '';
    document.getElementById('uploadPreview').style.display = 'none';
    document.getElementById('uploadPreviewContent').textContent = '';
    document.getElementById('uploadHydraResult').style.display = 'none';
    document.getElementById('uploadProgressWrap').style.display = 'none';
    document.getElementById('uploadResult').style.display = 'none';
    document.getElementById('uploadSubmitBtn').disabled = true;
    _selectedUploadFile = null;
    
    // 刷新上传列表
    refreshUploadList();
}

function closeUploadDialog() {
    const dialog = document.getElementById('uploadDialog');
    if (dialog) dialog.classList.remove('show');
}

// 携带当前脚本内容快速上传
function quickUploadScript() {
    openUploadDialog();
    // 自动填充脚本内容
    const content = window._batSourceContent || window._shContent || '';
    if (content) {
        const preview = document.getElementById('uploadPreview');
        const contentEl = document.getElementById('uploadPreviewContent');
        preview.style.display = '';
        contentEl.textContent = content.substring(0, 2000);
        document.getElementById('uploadFileInfo').textContent = `当前脚本（${content.split('\\n').length} 行）`;
    }
}

function onUploadFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    // 检查扩展名
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    const allowed = ['.bat', '.cmd', '.sh', '.txt'];
    if (!allowed.includes(ext)) {
        showToast('仅支持 .bat/.cmd/.sh/.txt 格式');
        event.target.value = '';
        return;
    }
    
    // 检查大小
    if (file.size > 1024 * 1024) {
        showToast('文件超过 1MB 限制');
        event.target.value = '';
        return;
    }
    
    _selectedUploadFile = file;
    document.getElementById('uploadSubmitBtn').disabled = false;
    document.getElementById('uploadFileInfo').textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    
    // 预览前 20 行
    const reader = new FileReader();
    reader.onload = function(e) {
        const content = e.target.result;
        const lines = content.split('\\n');
        const previewLines = lines.slice(0, 20);
        const preview = document.getElementById('uploadPreview');
        const contentEl = document.getElementById('uploadPreviewContent');
        preview.style.display = '';
        contentEl.textContent = previewLines.join('\\n') + (lines.length > 20 ? '\\n...' : '');
        document.getElementById('uploadTotalLines').textContent = `共 ${lines.length} 行`;
        
        // 自动检测脚本类型
        const typeSelect = document.getElementById('uploadScriptType');
        if (file.name.endsWith('.bat') || file.name.endsWith('.cmd')) typeSelect.value = 'bat';
        else if (file.name.endsWith('.sh')) typeSelect.value = 'sh';
        else typeSelect.value = 'auto';
    };
    reader.readAsText(file);
}

async function submitUpload() {
    if (!_selectedUploadFile) return;
    
    const formData = new FormData();
    formData.append('file', _selectedUploadFile);
    formData.append('brand', document.getElementById('uploadBrand').value.trim());
    formData.append('device_model', document.getElementById('uploadModel').value.trim());
    
    const btn = document.getElementById('uploadSubmitBtn');
    const progressWrap = document.getElementById('uploadProgressWrap');
    const progressBar = document.getElementById('uploadProgressBar');
    const result = document.getElementById('uploadResult');
    
    btn.disabled = true;
    btn.textContent = '上传中...';
    progressWrap.style.display = '';
    progressBar.style.width = '30%';
    result.style.display = 'none';
    
    try {
        // 用 XMLHttpRequest 实现进度跟踪
        const xhr = new XMLHttpRequest();
        
        const resultPromise = new Promise((resolve, reject) => {
            xhr.upload.onprogress = function(e) {
                if (e.lengthComputable) {
                    const pct = Math.round(e.loaded / e.total * 70);
                    progressBar.style.width = (30 + pct) + '%';
                }
            };
            
            xhr.onload = function() {
                progressBar.style.width = '100%';
                try {
                    const resp = JSON.parse(xhr.responseText);
                    resolve(resp);
                } catch(e) {
                    reject(new Error('解析响应失败'));
                }
            };
            
            xhr.onerror = function() {
                reject(new Error('网络错误'));
            };
        });
        
        const baseUrl = window.BACKEND_API_URL || '';
        xhr.open('POST', baseUrl + '/api/script/upload', true);
        xhr.send(formData);
        
        const resp = await resultPromise;
        
        result.style.display = '';
        
        if (resp.success) {
            result.className = 'upload-result success';
            let msg = `✅ 上传成功！${resp.uploaded_to_openlist ? '已同步到样本库' : '（本地保存）'}`;
            
            if (resp.hydra_result && resp.hydra_result.step_count > 0) {
                msg += `\\nHydra 解析：${resp.hydra_result.step_count} 步`;
                // 显示 Hydra 结果
                const hrEl = document.getElementById('uploadHydraResult');
                hrEl.style.display = '';
                document.getElementById('uploadHydraSteps').textContent = resp.hydra_result.step_count;
                document.getElementById('uploadHydraType').textContent = resp.hydra_result.script_type || '未知';
                document.getElementById('uploadHydraSimple').textContent = resp.hydra_result.is_simple ? '✅ 简单脚本' : '⚠️ 复杂脚本';
            }
            
            result.textContent = msg;
            // 刷新列表
            refreshUploadList();
        } else {
            result.className = 'upload-result error';
            result.textContent = `❌ ${resp.message || '上传失败'}`;
        }
    } catch(e) {
        result.style.display = '';
        result.className = 'upload-result error';
        result.textContent = `❌ 上传出错：${e.message}`;
    } finally {
        btn.disabled = false;
        btn.textContent = '确认上传';
        setTimeout(() => { progressWrap.style.display = 'none'; }, 2000);
    }
}

// 上传对话框点击外部关闭
document.addEventListener('click', function(e) {
    const dialog = document.getElementById('uploadDialog');
    if (dialog && dialog.classList.contains('show')) {
        if (e.target === dialog) closeUploadDialog();
    }
});