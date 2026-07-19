// flash_tool/static/js/components/webusb.js
// ====================================================================
// WebUSB Fastboot / ADB 实现（基于 fastboot.mjs / adb.bundle.mjs）
//
// 本文件为 ES 模块，通过 import 引入第三方协议库：
//   - static/js/lib/fastboot.mjs   : FastbootDevice / WebUsbTransport
//   - static/js/lib/adb.bundle.mjs : Adb / AdbDaemonTransport / AdbWebUsbBackend
//
// 对外仍以全局函数 / 全局变量形式暴露，保持与项目其余部分（classic 脚本）兼容：
//   window.webusbFastboot, window.webusbAdb, window.selectedUsbDevice
//   window.webusbFastbootReady, window.webusbAdbReady, window.deviceMode ...
//   detectWebUsbDevice / runWebUsbFastbootCommand / doWebUsbBatchFlash ...
// ====================================================================

import {
    FastbootDevice,
    WebUsbTransport,
    FASTBOOT_USB_FILTER,
    setLogLevel as fbSetLogLevel,
} from '../lib/fastboot.mjs';

import {
    Adb,
    AdbDaemonTransport,
    AdbWebUsbBackend,
    ADB_DEFAULT_AUTHENTICATORS,
    ADB_DEFAULT_DEVICE_FILTER,
} from '../lib/adb.bundle.mjs';

// 让 fastboot.mjs 的内部日志输出到控制台，便于排错
try { fbSetLogLevel(3); } catch (e) { /* LogLevel.Debug */ }

// ====================================================================
// ADB 主机密钥凭据存储（WebCrypto 生成 RSA-2048，持久化到 localStorage）
// ====================================================================
// adb.bundle.mjs 内置的签名器从密钥 buffer 中按固定偏移读取 n / d：
//   n : offset 38 , 长度 256 字节, 大端
//   d : offset 303, 长度 256 字节, 大端
// 因此我们用 WebCrypto 生成 RSASSA-PKCS1-v1_5 (e=65537) 密钥，导出 JWK，
// 取其中的 n / d（base64url 大端无符号整数），左填充到 256 字节后写入对应偏移。
const ADB_KEY_STORAGE = 'webusb_adb_rsa_keys';
const ADB_KEY_BUF_LEN = 559; // 303 + 256

function base64UrlToUint8(b64url) {
    const b64 = String(b64url || '').replace(/-/g, '+').replace(/_/g, '/');
    const pad = b64.length % 4 ? '='.repeat(4 - (b64.length % 4)) : '';
    const bin = atob(b64 + pad);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
}

function padLeft256(bytes) {
    if (bytes.length === 256) return bytes;
    if (bytes.length > 256) return bytes.subarray(bytes.length - 256);
    const out = new Uint8Array(256);
    out.set(bytes, 256 - bytes.length);
    return out;
}

function buildAdbPrivateKeyBuffer(nB64Url, dB64Url) {
    const buf = new Uint8Array(ADB_KEY_BUF_LEN);
    buf.set(padLeft256(base64UrlToUint8(nB64Url)), 38);   // n @ 38
    buf.set(padLeft256(base64UrlToUint8(dB64Url)), 303);  // d @ 303
    return buf;
}

class WebUsbAdbCredentialStore {
    constructor() {
        this._keys = [];
        this._load();
    }

    _load() {
        try {
            const raw = localStorage.getItem(ADB_KEY_STORAGE);
            if (raw) {
                const arr = JSON.parse(raw);
                if (Array.isArray(arr)) {
                    this._keys = arr.map(k => ({
                        name: k.name || 'webusb-adb-key',
                        buffer: base64UrlToUint8(k.buffer),
                    }));
                }
            }
        } catch (e) {
            console.warn('[webusb] 加载 ADB 密钥失败:', e);
        }
    }

    _save() {
        try {
            const arr = this._keys.map(k => ({
                name: k.name,
                buffer: uint8ToBase64Url(k.buffer),
            }));
            localStorage.setItem(ADB_KEY_STORAGE, JSON.stringify(arr));
        } catch (e) {
            console.warn('[webusb] 保存 ADB 密钥失败:', e);
        }
    }

    async *iterateKeys() {
        for (const key of this._keys) {
            yield key;
        }
    }

    async generateKey() {
        const keyPair = await crypto.subtle.generateKey(
            {
                name: 'RSASSA-PKCS1-v1_5',
                modulusLength: 2048,
                publicExponent: new Uint8Array([1, 0, 1]), // 65537
                hash: 'SHA-1',
            },
            true,
            ['sign', 'verify']
        );
        const jwk = await crypto.subtle.exportKey('jwk', keyPair.privateKey);
        const buffer = buildAdbPrivateKeyBuffer(jwk.n, jwk.d);
        const key = { name: 'webusb-adb-key', buffer };
        this._keys.push(key);
        this._save();
        return key;
    }
}

function uint8ToBase64Url(bytes) {
    let bin = '';
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
        bin += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }
    return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

let _credentialStore = null;
function getAdbCredentialStore() {
    if (!_credentialStore) {
        _credentialStore = new WebUsbAdbCredentialStore();
    }
    return _credentialStore;
}

// ====================================================================
// WebUsbFastbootAdapter — 包装 FastbootDevice，保留旧版全局 API
// ====================================================================
class WebUsbFastbootAdapter {
    constructor(fbDevice) {
        this._fb = fbDevice;
    }

    get raw() { return this._fb; }

    /** 执行一条 Fastboot 命令（智能翻译） */
    async command(cmdStr) {
        const s = String(cmdStr || '').trim();
        const lower = s.toLowerCase();

        // erase:partition — 使用 fb.erase（自动 A/B 槽位解析）
        if (lower.startsWith('erase:')) {
            const part = s.slice(6).trim();
            await this._fb.erase(part);
            return 'OKAY';
        }

        // reboot 系列命令
        if (lower === 'reboot' || lower === 'reboot-system' || lower === 'reboot:system') {
            await this._fb.reboot('');
            return 'OKAY';
        }
        if (lower === 'reboot-bootloader' || lower === 'reboot:bootloader') {
            await this._fb.reboot('bootloader');
            return 'OKAY';
        }
        if (lower === 'reboot-recovery' || lower === 'reboot:recovery') {
            await this._fb.reboot('recovery');
            return 'OKAY';
        }
        if (lower === 'reboot-fastbootd' || lower === 'reboot:fastbootd') {
            await this._fb.reboot('fastboot');
            return 'OKAY';
        }
        if (lower.startsWith('reboot-') || lower.startsWith('reboot:')) {
            const mode = s.split(/[-:]/)[1].trim();
            await this._fb.reboot(mode);
            return 'OKAY';
        }

        // flashing <sub> / flashing:<sub>
        if (lower.startsWith('flashing ')) {
            return await this._fb.runCommand('flashing:' + s.slice(9).trim());
        }
        if (lower.startsWith('flashing:')) {
            return await this._fb.runCommand(s);
        }

        // oem <sub>
        if (lower.startsWith('oem ')) {
            return await this._fb.runCommand(s);
        }

        // set_active:slot
        if (lower.startsWith('set_active:')) {
            return await this._fb.runCommand('set_active:' + s.slice(11).trim());
        }

        // getvar:xxx — 特殊处理 getvar:all
        if (lower === 'getvar:all') {
            return await this._getAllVars();
        }
        if (lower.startsWith('getvar:')) {
            return await this._fb.getVariable(s.slice(7).trim());
        }

        // continue
        if (lower === 'continue') {
            return await this._fb.runCommand('continue');
        }

        // 默认：直接发送原始命令
        return await this._fb.runCommand(s);
    }

    /** 刷写分区 */
    async flash(partition, bytes, onProgress) {
        const blob = new Blob([bytes]);
        const wrappedProgress = onProgress
            ? (sent, total) => {
                const pct = total > 0 ? Math.round((sent / total) * 100) : 0;
                onProgress(pct);
            }
            : undefined;
        await this._fb.flashBlob(partition, blob, wrappedProgress);
    }

    /** CLI 风格命令入口（兼容旧版 fastbootCommand） */
    async fastbootCommand(cmdStr) {
        const s = String(cmdStr || '').trim();
        // 去掉 "fastboot " 前缀
        const stripped = s.toLowerCase().startsWith('fastboot ') ? s.slice(9) : s;
        const parts = stripped.split(/\s+/);
        const cmd0 = (parts[0] || '').toLowerCase();

        if (cmd0 === 'flash') {
            throw new Error('flash 命令请使用 webusbFastboot.flash()');
        }
        if (cmd0 === 'erase') {
            await this._fb.erase(parts[1]);
            return 'OKAY';
        }
        if (cmd0 === 'reboot') {
            const target = parts[1] || '';
            // system → 空字符串（普通重启）
            const mode = (target === 'system' || target === '') ? '' : target;
            await this._fb.reboot(mode);
            return 'OKAY';
        }
        if (cmd0 === 'getvar') {
            if (!parts[1] || parts[1] === 'all') return await this._getAllVars();
            return await this._fb.getVariable(parts[1]);
        }
        if (cmd0 === 'set_active') {
            return await this._fb.runCommand('set_active:' + (parts[1] || ''));
        }
        if (cmd0 === 'oem') {
            return await this._fb.runCommand('oem ' + parts.slice(1).join(' '));
        }
        if (cmd0 === 'flashing') {
            return await this._fb.runCommand('flashing:' + parts.slice(1).join(':'));
        }
        if (cmd0 === 'continue') {
            return await this._fb.runCommand('continue');
        }

        // 默认：用冒号连接
        if (parts.length >= 2) {
            return await this._fb.runCommand(parts[0] + ':' + parts.slice(1).join(':'));
        }
        return await this._fb.runCommand(stripped);
    }

    /** 获取设备所有变量（模拟 getvar:all） */
    async _getAllVars() {
        const vars = {};
        const transport = this._fb._transport;
        // 发送 getvar:all
        const cmd = new TextEncoder().encode('getvar:all');
        await transport.send(cmd);
        // 读取 INFO 响应直到 OKAY/FAIL
        const results = [];
        for (let i = 0; i < 100; i++) {
            const res = await transport.readTransfer();
            const status = new TextDecoder().decode(res.slice(0, 4));
            const msg = new TextDecoder().decode(res.slice(4)).replace(/\0.*$/, '').trim();
            if (status === 'INFO') {
                const eqIdx = msg.indexOf(':');
                if (eqIdx > 0) {
                    vars[msg.slice(0, eqIdx)] = msg.slice(eqIdx + 1).trim();
                }
                results.push(msg);
            } else if (status === 'OKAY') {
                break;
            } else if (status === 'FAIL') {
                throw new Error('Fastboot getvar:all 失败: ' + msg);
            }
        }
        return JSON.stringify(vars);
    }
}

// ====================================================================
// WebUsbAdbAdapter — 包装 Adb，保留旧版全局 API
// ====================================================================
class WebUsbAdbAdapter {
    constructor(adbInstance) {
        this._adb = adbInstance;
    }

    get raw() { return this._adb; }

    async shell(cmd) {
        return await this._adb.createSocketAndWait('shell:' + cmd);
    }

    async reboot(target) {
        // system → 空字符串（普通重启）
        const mode = (!target || target === 'system') ? '' : target;
        return await this._adb.power.reboot(mode);
    }

    async adbCommand(cmdStr) {
        const s = String(cmdStr || '').trim();
        const parts = s.split(/\s+/);
        const cmd0 = (parts[0] || '').toLowerCase();

        if (cmd0 === 'devices') return '';
        if (cmd0 === 'reboot') {
            await this.reboot(parts.slice(1).join(' '));
            return '';
        }
        if (cmd0 === 'shell') return await this.shell(parts.slice(1).join(' '));
        if (cmd0 === 'get-state') return (await this.shell('echo device')).trim() || 'device';
        return await this.shell(s);
    }

    async close() {
        try {
            await this._adb.dispose();
        } catch (e) { /* ignore */ }
    }
}

// ====================================================================
// 设备接口检测
// ====================================================================

/**
 * 检测设备当前模式（ADB / Fastboot）
 * ADB:      class=0xFF, subclass=0x42, protocol=0x01
 * Fastboot: class=0xFF, subclass=0x42, protocol=0x03
 */
function detectDeviceMode(device) {
    if (!device || !device.configuration) return 'none';
    const ifaces = device.configuration.interfaces;
    for (let i = 0; i < ifaces.length; i++) {
        const alt = ifaces[i].alternate;
        if (!alt) continue;
        if (alt.interfaceClass === 0xFF && alt.interfaceSubclass === 0x42) {
            if (alt.interfaceProtocol === 0x01) return 'adb';
            if (alt.interfaceProtocol === 0x03) return 'fastboot';
        }
    }
    return 'none';
}

// ====================================================================
// USB 接口声明函数
// ====================================================================

/**
 * 声明 ADB 接口并完成授权握手
 */
async function claimWebUsbInterface(device) {
    try {
        const backend = new AdbWebUsbBackend(device, [ADB_DEFAULT_DEVICE_FILTER], navigator.usb);
        const connection = await backend.connect();
        const transport = await AdbDaemonTransport.authenticate({
            serial: device.serialNumber || '',
            connection,
            credentialStore: getAdbCredentialStore(),
            authenticators: ADB_DEFAULT_AUTHENTICATORS,
        });
        const adb = new Adb(transport);
        webusbAdb = new WebUsbAdbAdapter(adb);
        webusbAdbReady = true;
        if (typeof writeLog === 'function') writeLog('WebUSB ADB 已连接（RSA 授权握手完成）', 'ok');
        return true;
    } catch (e) {
        if (typeof writeLog === 'function') writeLog('声明 ADB 接口失败：' + (e && e.message ? e.message : e), 'warn');
        return false;
    }
}

/**
 * 声明 Fastboot 接口
 */
async function claimWebUsbFastboot(device) {
    try {
        const transport = new WebUsbTransport(device, FASTBOOT_USB_FILTER);
        const fb = new FastbootDevice(transport);
        await fb.connect();
        webusbFastboot = new WebUsbFastbootAdapter(fb);
        webusbFastbootReady = true;
        if (typeof writeLog === 'function') writeLog('WebUSB Fastboot 已连接', 'ok');
        return true;
    } catch (e) {
        if (typeof writeLog === 'function') writeLog('声明 Fastboot 接口失败：' + (e && e.message ? e.message : e), 'warn');
        return false;
    }
}

// ====================================================================
// 命令路由
// ====================================================================

/**
 * runWebUsbFastbootCommand — 将命令对象路由到具体的 WebUSB 调用
 */
async function runWebUsbFastbootCommand(cmdObj) {
    if (!cmdObj || !cmdObj.command) throw new Error('无效的 WebUSB 命令对象');
    const cmd = cmdObj.command;
    switch (cmd) {
        case 'flash':
            if (!cmdObj.payload) throw new Error('flash 命令需要 payload');
            if (!webusbFastboot) throw new Error('WebUSB Fastboot 未连接');
            await webusbFastboot.flash(cmdObj.partition, cmdObj.payload);
            return '已刷写 ' + cmdObj.partition;
        case 'erase':
            if (!webusbFastboot) throw new Error('WebUSB Fastboot 未连接');
            if (typeof webusbEraseWithFallback === 'function') {
                await webusbEraseWithFallback(cmdObj.partition);
            } else {
                await webusbFastboot.command('erase:' + cmdObj.partition);
            }
            return '已擦除 ' + cmdObj.partition;
        case 'reboot':
            if (webusbFastbootReady && webusbFastboot) {
                await webusbFastboot.command('reboot-' + (cmdObj.target || 'system'));
                return '已发送重启到 ' + (cmdObj.target || 'system');
            }
            if (webusbAdbReady && webusbAdb) {
                await webusbAdb.reboot(cmdObj.target || '');
                return '已发送 ADB 重启到 ' + (cmdObj.target || '系统');
            }
            throw new Error('没有可用的 WebUSB 连接');
        case 'set_active':
            if (!webusbFastboot) throw new Error('WebUSB Fastboot 未连接');
            await webusbFastboot.command('set_active:' + cmdObj.slot);
            return '已设置槽位 ' + cmdObj.slot;
        case 'getvar':
            if (!webusbFastboot) throw new Error('WebUSB Fastboot 未连接');
            return await webusbFastboot.command('getvar:' + cmdObj.variable);
        case 'oem':
            if (!webusbFastboot) throw new Error('WebUSB Fastboot 未连接');
            return await webusbFastboot.command('oem ' + cmdObj.sub);
        case 'flashing':
            if (!webusbFastboot) throw new Error('WebUSB Fastboot 未连接');
            return await webusbFastboot.command('flashing:' + cmdObj.sub);
        default:
            throw new Error('未知的 WebUSB 命令: ' + cmd);
    }
}

// ====================================================================
// 兼容函数（保持与原版一致）
// ====================================================================

function validateWebUsbScriptImages() {
    if (stepList.length === 0) return { ok: true, missing: [] };
    const missing = [];
    for (let i = 0; i < stepList.length; i++) {
        const step = stepList[i];
        if (step.type !== 'flash' || !step.fileName) continue;
        const cached = romImageCache[step.fileName];
        if (!cached || !cached.bytes || cached.bytes.length === 0) {
            missing.push(step.fileName);
        }
    }
    return { ok: missing.length === 0, missing };
}

function fastbootArgsToWebUsbCommand(args) {
    if (!Array.isArray(args) || args.length === 0) return null;
    const cmd = String(args[0] || '').toLowerCase();
    if (cmd === 'flash') return { command: 'flash', partition: args[1], payload: args[2] || '' };
    if (cmd === 'erase') return { command: 'erase', partition: args[1] };
    if (cmd === 'reboot') return { command: 'reboot', target: args[1] || 'system' };
    if (cmd === 'set_active') return { command: 'set_active', slot: args[1] };
    if (cmd === 'getvar') return { command: 'getvar', variable: args[1] };
    if (cmd === 'oem') return { command: 'oem', sub: args.slice(1).join(' ') };
    if (cmd === 'flashing') return { command: 'flashing', sub: args.slice(1).join(' ') };
    return null;
}

function showWebUsbSelectedDevice(device) {
    const card = document.getElementById('webusbDeviceCard');
    if (!card) return;
    const info = document.getElementById('webusbDeviceInfo');
    if (!device) {
        card.style.display = 'none';
        info.textContent = '';
        return;
    }
    card.style.display = 'block';
    const name = device.productName || device.serialNumber || '未知设备';
    const serial = device.serialNumber || '未知';
    info.innerHTML = '<strong>' + escHtml(name) + '</strong><br>序列号：' + escHtml(serial);
    if (typeof writeLog === 'function') writeLog('已选择 WebUSB 设备：' + name + '（' + serial + '）', 'ok');
}

async function detectWebUsbDevice() {
    if (!navigator.usb) {
        if (typeof setModuleStatus === 'function') setModuleStatus('single', 'WebUSB 状态：当前浏览器不支持 WebUSB。', 'err');
        if (typeof writeLog === 'function') writeLog('当前浏览器不支持 WebUSB', 'err');
        return false;
    }
    if (typeof setModuleStatus === 'function') setModuleStatus('single', 'WebUSB 状态：正在请求设备…', 'info');
    try {
        const device = await navigator.usb.requestDevice({ filters: [] });
        await device.open();
        selectedUsbDevice = device;
        if (typeof showWebUsbSelectedDevice === 'function') showWebUsbSelectedDevice(device);

        const mode = detectDeviceMode(device);
        if (mode === 'adb') {
            const ok = await claimWebUsbInterface(device);
            if (ok) {
                deviceMode = 'webusb-adb';
                if (typeof setModuleStatus === 'function') setModuleStatus('single', 'WebUSB 状态：ADB 接口已就绪。', 'ok');
                if (typeof writeLog === 'function') writeLog('WebUSB ADB 设备已连接', 'ok');
                if (typeof updateBtnState === 'function') updateBtnState();
                return true;
            }
        } else if (mode === 'fastboot') {
            const ok = await claimWebUsbFastboot(device);
            if (ok) {
                deviceMode = 'webusb-fastboot';
                if (typeof setModuleStatus === 'function') setModuleStatus('single', 'WebUSB 状态：Fastboot 接口已就绪。', 'ok');
                if (typeof writeLog === 'function') writeLog('WebUSB Fastboot 设备已连接', 'ok');
                if (typeof refreshDeviceInfoAuto === 'function') await refreshDeviceInfoAuto();
                if (typeof updateBtnState === 'function') updateBtnState();
                return true;
            }
        } else {
            // 未检测到已知接口，尝试两种
            const adbOk = await claimWebUsbInterface(device);
            if (adbOk) {
                deviceMode = 'webusb-adb';
                if (typeof setModuleStatus === 'function') setModuleStatus('single', 'WebUSB 状态：ADB 接口已就绪。', 'ok');
                if (typeof updateBtnState === 'function') updateBtnState();
                return true;
            }
            const fbOk = await claimWebUsbFastboot(device);
            if (fbOk) {
                deviceMode = 'webusb-fastboot';
                if (typeof setModuleStatus === 'function') setModuleStatus('single', 'WebUSB 状态：Fastboot 接口已就绪。', 'ok');
                if (typeof refreshDeviceInfoAuto === 'function') await refreshDeviceInfoAuto();
                if (typeof updateBtnState === 'function') updateBtnState();
                return true;
            }
        }
        if (typeof setModuleStatus === 'function') setModuleStatus('single', 'WebUSB 状态：设备已连接，但未识别到 ADB/Fastboot 接口。', 'warn');
        return false;
    } catch (e) {
        if (typeof setModuleStatus === 'function') setModuleStatus('single', 'WebUSB 状态：连接失败：' + (e && e.message ? e.message : e), 'err');
        if (typeof writeLog === 'function') writeLog('WebUSB 连接失败：' + (e && e.message ? e.message : e), 'err');
        return false;
    }
}

async function waitForFastbootReconnect(timeoutMs) {
    timeoutMs = timeoutMs || 60000;
    const start = Date.now();
    if (typeof writeLog === 'function') writeLog('等待设备以 Fastboot 模式重新连接…', 'info');
    while (Date.now() - start < timeoutMs) {
        try {
            const res = await apiGet('/api/device');
            if (res.connected && res.count > 0) {
                canFastboot = true;
                deviceMode = 'fastboot';
                if (typeof writeLog === 'function') writeLog('Fastboot 设备已重新连接', 'ok');
                if (typeof refreshDeviceInfoAuto === 'function') await refreshDeviceInfoAuto();
                if (typeof updateBtnState === 'function') updateBtnState();
                return true;
            }
        } catch (e) { /* ignore */ }
        await sleep(2000);
    }
    if (typeof writeLog === 'function') writeLog('等待 Fastboot 重连超时', 'warn');
    return false;
}

async function recoverFastbootAfterScriptReboot(reason) {
    reason = reason || '';
    if (typeof writeLog === 'function') writeLog('检测到脚本重启断联' + (reason ? '（' + reason + '）' : '') + '，尝试恢复 Fastboot 连接…', 'info');
    canFastboot = false;
    canAdb = false;
    deviceMode = '';
    if (typeof setModuleStatus === 'function') setModuleStatus('batch', '线刷状态：设备重启中，正在等待 Fastboot 重连…', 'warn');
    if (typeof showModuleProgress === 'function') showModuleProgress('batch', '等待 Fastboot 重连…');
    const ok = await waitForFastbootReconnect(120000);
    if (ok) {
        if (typeof hideModuleProgress === 'function') hideModuleProgress('batch');
        if (typeof setModuleStatus === 'function') setModuleStatus('batch', '线刷状态：Fastboot 已重连，继续执行。', 'ok');
        return true;
    }
    if (typeof hideModuleProgress === 'function') hideModuleProgress('batch');
    if (typeof setModuleStatus === 'function') setModuleStatus('batch', '线刷状态：Fastboot 重连超时，请重新插拔设备并点击检测。', 'err');
    return false;
}

function pauseWebUsbBatchAfterReboot(stepIndex, reason) {
    reason = reason || '';
    if (typeof saveBackendReconnectCheckpoint === 'function') saveBackendReconnectCheckpoint(stepIndex, 'webusb-reboot' + (reason ? ':' + reason : ''));
    if (typeof writeLog === 'function') writeLog('脚本在第 ' + (stepIndex + 1) + ' 步触发重启，已暂停并保存断点。请等待设备以 Fastboot 重连后点击"恢复线刷"。', 'warn');
    if (typeof setModuleStatus === 'function') setModuleStatus('batch', '线刷状态：第 ' + (stepIndex + 1) + ' 步重启，已暂停，等待重连恢复。', 'warn');
    if (typeof showModuleProgress === 'function') showModuleProgress('batch', '等待 Fastboot 重连…');
    if (typeof updateBatchActionState === 'function') updateBatchActionState();
}

function isExpectedRebootDisconnect(res) {
    if (!res) return false;
    const text = String(res.error || res.message || '').toLowerCase();
    return /device not found|no devices|offline|disconnected|timeout|reset|reboot/i.test(text);
}

async function doWebUsbBatchFlash() {
    if (stepList.length === 0) {
        if (typeof showToast === 'function') showToast('请先解析刷机脚本');
        return;
    }
    if (!webusbFastbootReady) {
        if (typeof showToast === 'function') showToast('请先连接 WebUSB Fastboot 设备');
        return;
    }
    const validation = validateWebUsbScriptImages();
    if (!validation.ok) {
        if (typeof showConfirm === 'function') {
            showConfirm(
                '缺少镜像文件',
                '以下镜像未缓存，WebUSB 线刷需要全部镜像已下载：\n' + validation.missing.join('\n') + '\n\n请先在 ROM 管理中下载这些镜像，或在后端模式下执行线刷（后端可按需读取）。',
                null,
                false
            );
        }
        return;
    }
    let resumeIndex = 0;
    if (typeof shouldAutoResumeAfterReconnect === 'function' && shouldAutoResumeAfterReconnect()) {
        try {
            const saved = localStorage.getItem('batch_progress');
            const data = JSON.parse(saved);
            resumeIndex = Math.max(0, Number(data.step_index || 0));
            if (typeof writeLog === 'function') writeLog('从断点恢复 WebUSB 线刷，起始步骤：' + (resumeIndex + 1), 'info');
        } catch (e) { /* ignore */ }
        if (typeof clearReconnectCheckpoint === 'function') clearReconnectCheckpoint();
    }
    batchRunning = true;
    batchPaused = false;
    batchCurrentIndex = resumeIndex;
    const btn = document.getElementById('batchFlashBtn');
    if (btn) btn.disabled = true;
    if (typeof showModuleProgress === 'function') showModuleProgress('batch', 'WebUSB 线刷 0/' + stepList.length);
    try {
        for (let i = resumeIndex; i < stepList.length; i++) {
            if (batchPaused) {
                if (typeof writeLog === 'function') writeLog('WebUSB 线刷已暂停', 'warn');
                if (typeof saveBackendReconnectCheckpoint === 'function') saveBackendReconnectCheckpoint(i, 'paused');
                break;
            }
            batchCurrentIndex = i;
            const step = stepList[i];
            if (typeof updateModuleProgress === 'function') {
                updateModuleProgress('batch', Math.round((i / stepList.length) * 100), '第 ' + (i + 1) + '/' + stepList.length + ' 步：' + (step.raw || step.type));
            }
            appendBatchOutput('[' + (i + 1) + '/' + stepList.length + '] ' + (step.raw || step.type) + ' ' + (step.part || '') + ' ' + (step.fileName || ''));
            try {
                if (step.type === 'flash') {
                    const cached = romImageCache[step.fileName];
                    await runWebUsbFastbootCommand({ command: 'flash', partition: step.part, payload: cached.bytes });
                } else if (step.type === 'erase') {
                    if (typeof webusbEraseWithFallback === 'function') {
                        await webusbEraseWithFallback(step.part);
                    } else {
                        await runWebUsbFastbootCommand({ command: 'erase', partition: step.part });
                    }
                } else if (step.type === 'set_active') {
                    await runWebUsbFastbootCommand({ command: 'set_active', slot: step.part });
                } else if (step.type === 'reboot') {
                    await runWebUsbFastbootCommand({ command: 'reboot', target: step.part || 'system' });
                    if (i < stepList.length - 1) {
                        pauseWebUsbBatchAfterReboot(i, 'script-reboot');
                        return;
                    }
                } else if (step.type === 'oem') {
                    await runWebUsbFastbootCommand({ command: 'oem', sub: step.part });
                }
                appendBatchOutput('  -> 完成', 'ok');
            } catch (e) {
                appendBatchOutput('  -> 失败：' + (e && e.message ? e.message : e), 'err');
                if (isExpectedRebootDisconnect({ error: e && e.message })) {
                    pauseWebUsbBatchAfterReboot(i, 'disconnect:' + (e && e.message));
                    return;
                }
                throw e;
            }
            await sleep(300);
        }
        if (typeof hideModuleProgress === 'function') hideModuleProgress('batch');
        if (typeof setModuleStatus === 'function') setModuleStatus('batch', '线刷状态：WebUSB 线刷完成。', 'ok');
        if (typeof writeLog === 'function') writeLog('WebUSB 线刷全部完成', 'ok');
        if (typeof showToast === 'function') showToast('WebUSB 线刷完成');
        if (typeof clearReconnectCheckpoint === 'function') clearReconnectCheckpoint();
    } catch (e) {
        if (typeof hideModuleProgress === 'function') hideModuleProgress('batch');
        if (typeof setModuleStatus === 'function') setModuleStatus('batch', '线刷状态：WebUSB 线刷失败：' + (e && e.message ? e.message : e), 'err');
        if (typeof writeLog === 'function') writeLog('WebUSB 线刷失败：' + (e && e.message ? e.message : e), 'err');
        if (typeof showErrorCard === 'function') showErrorCard('WebUSB 线刷失败', (e && e.message ? e.message : e));
    } finally {
        batchRunning = false;
        if (btn) btn.disabled = false;
        if (typeof updateBatchActionState === 'function') updateBatchActionState();
    }
}

function appendBatchOutput(text, level) {
    level = level || 'info';
    const box = document.getElementById('batchOutputArea');
    if (box) {
        const line = document.createElement('div');
        line.className = 'batch-output-line batch-output-' + level;
        line.textContent = text;
        box.appendChild(line);
        box.scrollTop = box.scrollHeight;
    }
    if (typeof writeLog === 'function') writeLog(text, level);
}

// ====================================================================
// 暴露到 window（供 classic 脚本调用）
// ====================================================================
Object.assign(window, {
    claimWebUsbInterface,
    claimWebUsbFastboot,
    detectDeviceMode,
    detectWebUsbDevice,
    showWebUsbSelectedDevice,
    fastbootArgsToWebUsbCommand,
    runWebUsbFastbootCommand,
    validateWebUsbScriptImages,
    waitForFastbootReconnect,
    recoverFastbootAfterScriptReboot,
    pauseWebUsbBatchAfterReboot,
    isExpectedRebootDisconnect,
    doWebUsbBatchFlash,
    appendBatchOutput,
    getAdbCredentialStore,
    WebUsbFastbootAdapter,
    WebUsbAdbAdapter,
    WebUsbAdbCredentialStore,
});

// ============ 模块初始化 ============
if (typeof Modules !== 'undefined' && Modules.register) {
    Modules.register('webusb', [], function initWebusbModule() {
        console.log('[webusb] WebUSB 模块已初始化（fastboot.mjs + adb.bundle.mjs）');
        return true;
    });
}
