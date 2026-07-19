// static/js/components/parser-manager.js
// 解析器管理弹窗

(function() {
    'use strict';

    var _pendingOverwrite = null; // 等待覆盖确认的文件信息

    // WebDAV 默认配置
    var WD_DEFAULTS = {
        url: 'https://dav.jianguoyun.com/dav/',
        user: '1248331222@qq.com',
        pass: 'a9a69b5dz6ka58r4',
    };

    // ============ 解析器开发指南（内嵌） ============
    var GUIDE_CONTENT = [
'# 天树刷机 — 解析器开发指南',
'',
'解析器是一个独立的 JS 模块，负责将刷机脚本转换为后端可执行的步骤列表。本文档只规定两件事：我们给你什么，你必须返回什么。解析器内部如何处理脚本，完全由开发者自行决定。',
'',
'## 匹配机制',
'',
'解析器文件名必须与分类器产出的特征键精确匹配，格式为 `特征键.js`。分类器扫描脚本语法特征并组合成键，如 `bat_for_if_percent`，对应的解析器文件名就是 `bat_for_if_percent.js`。匹配失败时系统提示用户安装对应解析器，不做降级。',
'',
'### BAT 脚本特征',
'',
'| 类别 | 变体 | 匹配规则 |',
'|------|------|----------|',
'| loop | `for` / `for_f` / `nested_for` | `for %%X in (` / `for /f` / 2 个以上 for 循环 |',
'| condition | `if` | 任何 `if` 语句 |',
'| branch | `goto` / `call` / `interactive` | `goto :label` 或 `goto label` / `call :` / `set /p` 或 `choice /` |',
'| variable | `percent` / `delayed` | `%VAR%` 或 `%~dp0` / `!VAR!` |',
'| tool_ref | `direct` / `indirect` / `prefixed` | 行首直接调用 `fastboot`/`adb` / `%...TOOL/PATH...%` / `"fastboot.exe"` |',
'',
'### SH 脚本特征',
'',
'| 类别 | 变体 | 匹配规则 |',
'|------|------|----------|',
'| loop | `for` / `cfor` / `while` | `for X in` / `for ((` / `while` |',
'| condition | `if` / `case` | `if [` / `case X in` |',
'| function_def | `defined` | `function X` 或 `X()` + `{` |',
'| expansion | `dollar_sub` / `backtick` / `dollar_brace` | `$( )` / `` ` `` / `${ }` |',
'| structure | `pipe` / `redirect` | `|` / `<` `>` |',
'| path_util | `dirname` | `dirname` / `readlink` / `pwd` / `realpath` |',
'',
'特征键格式为 `脚本类型_变体1_变体2_...`，`none` 变体跳过，按类别定义顺序排列。例如包含 `for` 循环、`if` 条件、`%VAR%` 变量的 BAT 脚本，特征键为 `bat_for_if_percent`。',
'',
'一个只包含 `fastboot flash boot boot.img` 和 `fastboot reboot` 的简单 BAT 脚本，特征键为 `bat_direct`，对应解析器文件名 `bat_direct.js`。',
'',
'分类器还会检测参数占位符（BAT 的 `%*` `%1`-`%9`，SH 的 `$@` `$1`-`$9`），检测到时前端会显示参数输入框，用户填写的值通过 `ctx.extraArgs` 传入解析器。',
'',
'## 我们提供的接口',
'',
'### 调用签名',
'',
'系统通过 `import()` 加载解析器模块，调用其导出的 `parse` 函数：',
'',
'```javascript',
'parse(content, ctx)',
'```',
'',
'- `content`：`string`，脚本完整文本',
'- `ctx`：`object`，上下文对象，见下表',
'',
'解析器可以使用 `export function parse` 或 `export default function parse` 导出。CommonJS 格式（`module.exports = { parse: function... }`）也支持，系统会自动转换。',
'',
'### 上下文对象 ctx',
'',
'| 字段 | 类型 | 说明 |',
'|------|------|------|',
'| `fileApi` | object | 文件系统 API 实例，详见下文 |',
'| `extraArgs` | string | 用户填写的脚本参数，可能为空字符串 |',
'| `romDir` | string | 脚本所在目录的绝对路径 |',
'| `scriptPath` | string | 脚本文件的绝对路径 |',
'',
'### 路径可用性',
'',
'后端模式下，用户通过内置文件管理器选择脚本文件。文件管理器浏览整个手机文件系统，选择文件后系统获得脚本的绝对路径，并自动计算 `romDir`（脚本所在目录）。因此：',
'',
'| 场景 | romDir / scriptPath | fileApi |',
'|------|---------------------|---------|',
'| 后端模式 + 文件管理器选择 | 有值（绝对路径） | 全部可用 |',
'| 后端模式 + 浏览器选择器 | 空字符串 | 全部可用 |',
'| WebUSB 模式 | 空字符串 | 不可用（返回空值） |',
'',
'`ctx.scriptPath` 是脚本文件的绝对路径（如 `/sdcard/rom/flash.bat`），`ctx.romDir` 是脚本所在目录（如 `/sdcard/rom`）。解析器用 `ctx.romDir` 拼接脚本中的相对路径（如 `boot.img` → `/sdcard/rom/boot.img`）。',
'',
'### FileApi 接口',
'',
'解析器通过 `ctx.fileApi` 访问后端文件系统。后端模式下全部可用；WebUSB 模式下不可用，调用返回空值或 false。',
'',
'| 方法 | 签名 | 返回值 | 说明 |',
'|------|------|--------|------|',
'| `list` | `list(dirPath, pattern?)` | `Promise<{name, path, type, size}[]>` | 列出目录内容 |',
'| `exists` | `exists(filePath)` | `Promise<boolean>` | 检查文件或目录是否存在 |',
'| `glob` | `glob(pattern, basePath)` | `Promise<string[]>` | 展开通配符，返回匹配文件的绝对路径列表 |',
'| `read` | `read(filePath, encoding?)` | `Promise<string>` | 读取文本文件，自动检测编码（utf-8/gbk/gb2312） |',
'| `readWithMeta` | `readWithMeta(filePath, encoding?)` | `Promise<{content, abs_path}>` | 读取文件并返回绝对路径 |',
'| `readBinary` | `readBinary(filePath)` | `Promise<Uint8Array>` | 读取二进制文件 |',
'| `mkdir` | `mkdir(dirPath)` | `Promise<void>` | 创建目录（递归） |',
'| `remove` | `remove(filePath)` | `Promise<void>` | 删除文件或目录 |',
'| `copy` | `copy(src, dst)` | `Promise<void>` | 复制文件或目录 |',
'| `move` | `move(src, dst)` | `Promise<void>` | 移动文件或目录 |',
'',
'## 解析器必须返回的内容',
'',
'解析器的返回值会被步骤列表和后端执行器读取。支持以下四种返回形式，选择哪一种由开发者根据需要决定。',
'',
'### 形式一：步骤数组',
'',
'直接返回步骤对象数组。',
'',
'```javascript',
'export function parse(content, ctx) {',
'    return [',
'        { type: \'flash\', partition: \'boot\', imagePath: \'/sdcard/boot.img\', raw: \'fastboot flash boot /sdcard/boot.img\', risk: \'MEDIUM\' },',
'        { type: \'reboot\', target: \'system\', raw: \'fastboot reboot\', risk: \'LOW\' },',
'    ];',
'}',
'```',
'',
'### 形式二：带元信息的对象',
'',
'返回包含 `steps` 数组的对象，可附加参数提示信息。',
'',
'```javascript',
'export function parse(content, ctx) {',
'    return {',
'        steps: [ /* 步骤对象 */ ],',
'        hasScriptParams: true,',
'        scriptParamHint: \'请输入序列号\',',
'    };',
'}',
'```',
'',
'### 形式三：Promise',
'',
'返回 Promise，resolve 为步骤数组或带元信息的对象。',
'',
'```javascript',
'export async function parse(content, ctx) {',
'    const files = await ctx.fileApi.glob(\'*.img\', ctx.romDir);',
'    return files.map(f => ({',
'        type: \'flash\',',
'        partition: f.split(\'/\').pop().replace(\'.img\', \'\'),',
'        imagePath: f,',
'        raw: `fastboot flash ${f.split(\'/\').pop().replace(\'.img\', \'\')} ${f}`,',
'        risk: \'MEDIUM\',',
'    }));',
'}',
'```',
'',
'### 形式四：Async Generator',
'',
'需要交互式解析时，返回 async generator，逐步 `yield` 步骤或交互请求。',
'',
'```javascript',
'export async function* parse(content, ctx) {',
'    yield { type: \'step\', step: { type: \'flash\', partition: \'boot\', imagePath: \'/path/boot.img\', raw: \'fastboot flash boot /path/boot.img\', risk: \'MEDIUM\' } };',
'',
'    const userChoice = yield { type: \'choice\', prompt: \'请选择刷写方式\', options: [\'全部刷写\', \'仅 boot\'] };',
'',
'    if (userChoice === 0) {',
'        yield { type: \'step\', step: { type: \'flash\', partition: \'system\', imagePath: \'/path/system.img\', raw: \'fastboot flash system /path/system.img\', risk: \'MEDIUM\' } };',
'    }',
'}',
'```',
'',
'generator yield 值的格式：',
'',
'| yield 值 | 含义 |',
'|----------|------|',
'| `{ type: \'step\', step: { 步骤对象 } }` | 追加一个步骤到列表 |',
'| `{ type: \'choice\', prompt: string, options: string[] }` | 暂停，弹出选择框，用户选择后返回索引（0-based） |',
'| `{ type: \'confirm\', prompt: string }` | 暂停，弹出确认框 |',
'',
'如果 yield 的值没有 `type` 字段，或 `type` 不是 `choice`/`confirm`，系统将其视为步骤对象直接追加。',
'',
'#### ⚠️ Generator 模式关键规则（易错点）',
'',
'**1. `yield` 只能出现在 `async function*` 中（带星号）**',
'',
'普通 `async function` 中使用 yield 会报 `Unexpected strict mode reserved word` 语法错误。',
'',
'```javascript',
'// ❌ 错误：async function（无星号）中使用 yield',
'async function executeLine(line) {',
'    if (step) yield { type: \'step\', step: step };  // 语法错误！',
'}',
'',
'// ✅ 正确：async function*（带星号）中使用 yield',
'async function* executeLine(line) {',
'    if (step) yield { type: \'step\', step: step };',
'}',
'```',
'',
'**2. 调用含 yield 的函数必须用 `yield*` 委托，不能用 `await`**',
'',
'```javascript',
'// ❌ 错误：用 await 调用，yield 值会丢失',
'await executeLine(line);',
'',
'// ✅ 正确：用 yield* 委托，yield 值逐层向上传递',
'yield* executeLine(line);',
'```',
'',
'**3. 不使用 yield 的辅助函数保持普通 `async function`**',
'',
'```javascript',
'async function expandCollection(pattern) {',
'    return await ctx.fileApi.glob(pattern, dir);',
'}',
'var items = await expandCollection(col);  // 用 await',
'```',
'',
'**速查表：**',
'',
'| 函数内是否 yield | 函数声明 | 调用方式 |',
'|---|---|---|',
'| 是 | `async function*` | `yield* fn()` |',
'| 否 | `async function` | `await fn()` |',
'',
'## 步骤对象格式',
'',
'每个步骤对象描述一条后端要执行的命令。',
'',
'### 字段定义',
'',
'| 字段 | 类型 | 必填 | 说明 |',
'|------|------|------|------|',
'| `type` | string | 是 | 步骤类型，见下表 |',
'| `partition` | string | 视类型 | 目标分区名 |',
'| `imagePath` | string | 视类型 | 镜像文件绝对路径 |',
'| `raw` | string | 否 | 完整命令文本，提供时后端优先使用 |',
'| `risk` | string | 否 | 风险等级，默认 `MEDIUM`（仅用于内部记录，前端步骤列表不显示风险标签） |',
'| `params` | string | 否 | 附加参数 |',
'| `target` | string | 否 | 重启目标 |',
'| `prefixParams` | string | 否 | 前缀参数，放在 `flash` 命令之前（如 `--disable-verity`） |',
'| `condition` | string | 否 | 条件表达式，满足时才执行该步骤 |',
'',
'### 步骤类型',
'',
'| type | 用途 | 需要的字段 | 示例 raw |',
'|------|------|-----------|----------|',
'| `flash` | 刷写分区 | partition, imagePath | `fastboot flash boot /path/boot.img` |',
'| `erase` | 擦除分区 | partition | `fastboot erase userdata` |',
'| `reboot` | 重启 | target | `fastboot reboot bootloader` |',
'| `set_active` | 设置活动槽位 | partition (`a`/`b`) | `fastboot --set-active=a` |',
'| `getvar` | 查询变量 | raw | `fastboot getvar all` |',
'| `oem` | OEM 命令 | raw | `fastboot oem unlock` |',
'| `flashing` | flashing 子命令 | raw | `fastboot flashing unlock` |',
'| `shell` | ADB shell | raw | `adb shell pm list packages` |',
'| `raw` | 原始命令 | raw | 任意 fastboot/adb 命令 |',
'| `wait_reconnect` | 等待设备重连 | target (`bootloader`/`fastboot`) | — |',
'| `decompress` | 解压文件 | format, inputFile, outputFile | `zstd -d super.zst -o super.img` |',
'',
'### decompress 类型',
'',
'当脚本包含 `zstd.exe`、`7z`、`unzip` 等解压命令时，返回 `decompress` 类型步骤：',
'',
'```javascript',
'{',
'    type: \'decompress\',',
'    format: \'zstd\',           // zstd / 7z / zip',
'    inputFile: \'/path/super.zst\',',
'    outputFile: \'/path/super.img\',  // 可省略，自动去 .zst 后缀',
'    removeSource: true,       // 对应 --rm',
'    raw: \'zstd --rm -d super.zst -o super.img\',',
'    risk: \'LOW\'',
'}',
'```',
'',
'后端优先使用命令行工具（zstd/7z/unzip），回退 Python 库。',
'',
'### wait_reconnect 类型',
'',
'当脚本执行中需要设备重启并等待重新连接时，使用 `wait_reconnect` 类型。前端会显示带 🔄 图标的特殊样式，执行时后端会等待设备重新出现在指定模式后再继续。',
'',
'```javascript',
'{ type: \'wait_reconnect\', target: \'bootloader\', raw: \'wait for device reconnect\', risk: \'LOW\' }',
'```',
'',
'### 风险等级',
'',
'风险等级仅在内部记录和工作台风险评估中使用，前端步骤列表不再显示风险标签。',
'',
'| 值 | 含义 |',
'|------|------|',
'| `CRITICAL` | 极高（如刷写 xbl/preloader） |',
'| `HIGH` | 高（如擦除 userdata） |',
'| `MEDIUM` | 中（默认，如刷写 boot） |',
'| `LOW` | 低（如重启命令） |',
'',
'### 路径要求',
'',
'`imagePath` 应为绝对路径。刷机脚本中给出的镜像路径通常是相对路径（如 `boot.img`），解析器必须使用 `ctx.romDir` 将其拼接为绝对路径。后端不会对路径做额外拼接。',
'',
'当 `ctx.romDir` 为空时（WebUSB 模式或浏览器选择器），解析器无法生成绝对路径，保留相对路径即可——后端执行时会报文件不存在的错误，用户可手动修正。',
'',
'### 参数占位符处理（%* / %1-%9）',
'',
'当脚本包含 `%*` 或 `%1`-`%9` 时，系统采用**前端实时同步**机制：',
'',
'1. 分类器检测到占位符 → 前端显示参数输入框',
'2. 解析器**应保留 `%*` 在 `raw` 中**，不要自行替换',
'3. 前端检测步骤 raw 中的占位符，参数为空时移除占位符，非空时替换',
'4. 用户修改参数输入框时，实时同步到所有含占位符的步骤',
'5. 后端执行时也会做相同替换作为兜底',
'',
'```javascript',
'// ✅ 推荐：保留 %* 在 raw 中',
'steps.push({ type: \'raw\', raw: \'fastboot %* -w\', risk: \'LOW\' });',
'',
'// ❌ 不推荐：解析器自行替换（前端无法实时同步）',
'steps.push({ type: \'raw\', raw: \'fastboot \' + ctx.extraArgs + \' -w\' });',
'```',
'',
'| 占位符 | 替换规则 |',
'|--------|----------|',
'| `%*` | 替换为完整的 extraArgs（空则移除） |',
'| `%1`-`%9` | 替换为对应位置参数（无则移除） |',
'',
'当 extraArgs 为空时，所有占位符被移除，多余空格被清理。',
'',
'### 参数位置（prefixParams）',
'',
'对于 `flash` 类型的步骤，`prefixParams` 字段指定的参数会放在 `flash` 命令之前。后端构建命令的格式为：',
'',
'```',
'fastboot [prefixParams] flash <partition> <imagePath> [params]',
'```',
'',
'例如 `prefixParams: \'--disable-verity --disable-verification\'` 会生成：',
'',
'```',
'fastboot --disable-verity --disable-verification flash vbmeta /path/vbmeta.img',
'```',
'',
'这是谷歌官方标准写法，`--disable-verity` / `--disable-verification` 属于 `flash` 命令的全局刷写选项，规范上应放在 `flash` 之前。',
'',
'## 最小示例解析器',
'',
'以下是一个完整的最小可用解析器，对应特征键 `bat_direct`（包含直接调用 fastboot/adb 命令的 BAT 脚本）。',
'',
'```javascript',
'// bat_direct.js',
'// 适配特征键: bat_direct',
'// 适配脚本: 直接调用 fastboot/adb 命令的 BAT 线刷脚本',
'',
'export async function parse(content, ctx) {',
'    var steps = [];',
'    var romDir = ctx.romDir || \'\';',
'',
'    // 逐行解析',
'    var lines = content.split(\'\\n\');',
'    for (var i = 0; i < lines.length; i++) {',
'        var line = lines[i].trim();',
'',
'        // 跳过注释和空行',
'        if (!line || line.startsWith(\'::\') || line.startsWith(\'REM \')) continue;',
'',
'        // 注意：不要替换 %* 和 %1-%9，保留在 raw 中让前端实时同步',
'',
'        // fastboot flash <partition> <image>',
'        var flashMatch = line.match(/^fastboot\\s+flash\\s+(\\S+)\\s+(.+)/i);',
'        if (flashMatch) {',
'            var partition = flashMatch[1];',
'            var imagePath = flashMatch[2];',
'',
'            // 相对路径用 romDir 拼接为绝对路径',
'            if (romDir && !imagePath.startsWith(\'/\')) {',
'                imagePath = romDir + \'/\' + imagePath;',
'            }',
'',
'            // 如果含通配符，用 fileApi 展开',
'            if (imagePath.indexOf(\'*\') >= 0 || imagePath.indexOf(\'?\') >= 0) {',
'                var dir = imagePath.substring(0, imagePath.lastIndexOf(\'/\'));',
'                var pattern = imagePath.substring(imagePath.lastIndexOf(\'/\') + 1);',
'                var files = await ctx.fileApi.glob(pattern, dir);',
'                if (files.length > 0) imagePath = files[0];',
'            }',
'',
'            steps.push({',
'                type: \'flash\',',
'                partition: partition,',
'                imagePath: imagePath,',
'                raw: \'fastboot flash \' + partition + \' \' + imagePath,',
'                risk: \'MEDIUM\',',
'            });',
'            continue;',
'        }',
'',
'        // fastboot erase <partition>',
'        var eraseMatch = line.match(/^fastboot\\s+erase\\s+(\\S+)/i);',
'        if (eraseMatch) {',
'            steps.push({',
'                type: \'erase\',',
'                partition: eraseMatch[1],',
'                raw: line,',
'                risk: \'HIGH\',',
'            });',
'            continue;',
'        }',
'',
'        // fastboot reboot [target]',
'        var rebootMatch = line.match(/^fastboot\\s+reboot\\s*(\\S*)/i);',
'        if (rebootMatch) {',
'            steps.push({',
'                type: \'reboot\',',
'                target: rebootMatch[1] || \'system\',',
'                raw: line,',
'                risk: \'LOW\',',
'            });',
'            continue;',
'        }',
'',
'        // 其他 fastboot/adb 命令（含 %* 的命令也在此处理，保留占位符）',
'        if (/^(fastboot|adb)\\s+/i.test(line)) {',
'            steps.push({ type: \'raw\', raw: line, risk: \'MEDIUM\' });',
'        }',
'    }',
'',
'    return { steps: steps };',
'}',
'```',
'',
'这个解析器做了三件关键的事：',
'',
'1. **从 `ctx.romDir` 获取脚本目录**，用它与脚本中的相对路径（如 `boot.img`）拼接为绝对路径（如 `/sdcard/rom/boot.img`）',
'2. **调用 `ctx.fileApi.glob()` 展开通配符**，当脚本中出现 `*.img` 时通过后端文件系统 API 获取实际文件路径',
'3. **返回步骤数组**，每个步骤包含 `type`、`partition`、`imagePath`（绝对路径）、`raw`（完整命令）、`risk`',
'',
'## 安装与管理',
'',
'### 存储位置',
'',
'解析器存储在后端 `~/.skytree/parsers/` 目录。每个解析器是一个 `.js` 文件。后端每次列出解析器时自动扫描目录，手动放入文件即可完成安装，删除文件即可卸载。',
'',
'### 安装方式',
'',
'前端"解析器管理"弹窗提供三种安装方式：本地文件上传、URL 直链下载、WebDAV 服务器浏览安装。同名解析器已存在时弹出覆盖确认。',
'',
'WebDAV 安装支持配置弹窗，可保存 WebDAV 地址、用户名、密码到本地，下次使用时自动加载。默认配置指向坚果云 WebDAV 服务。',
'',
'### 热插拔',
'',
'安装和卸载不需要重启后端服务。已加载到内存的解析器有缓存，如需强制刷新可调用 `ParserRunner.clearCache()`。',
'',
'## 调试',
'',
'在浏览器控制台中可执行以下操作：',
'',
'```javascript',
'// 查看脚本分类结果',
'ScriptClassifier.classify(\'脚本内容\');',
'',
'// 查看已安装解析器',
'ParserRunner.listParsers().then(parsers => console.table(parsers));',
'',
'// 手动运行解析器',
'ParserRunner.run(\'bat_direct.js\', \'脚本内容\', {',
'    fileApi: FileApi,',
'    extraArgs: \'\',',
'    romDir: \'/sdcard/rom\',',
'    scriptPath: \'/sdcard/rom/flash.bat\',',
'});',
'```',
'',
'### 常见问题',
'',
'| 问题 | 原因 |',
'|------|------|',
'| `没有导出 parse 函数` | 使用 `export function parse` 或 `module.exports = { parse: function... }` |',
'| `解析器 xxx 未安装` | 文件名与分类器输出的特征键不一致 |',
'| 步骤执行报路径错误 | `imagePath` 不是绝对路径，或 `ctx.romDir` 为空 |',
'| `fileApi` 方法返回空 | WebUSB 模式下后端不可用 |',
'| `解析器内部错误: module is not defined` | CommonJS 格式会被自动转换，但如果代码中混合使用 require 和 export 可能出错 |',
'',
'## 相关文件',
'',
'| 文件 | 角色 |',
'|------|------|',
'| `static/js/core/classifier.js` | 分类器 |',
'| `static/js/core/parser-runner.js` | 解析器加载与运行 |',
'| `static/js/core/file-api.js` | FileApi 封装 |',
'| `static/js/components/file-picker.js` | 前端文件管理器 |',
'| `static/js/components/batch-new.js` | 线刷页面 |',
'| `static/js/components/parser-manager.js` | 解析器管理弹窗 |',
'| `routes/api_parsers.py` | 后端解析器管理 API |',
'| `routes/api_fs.py` | 后端文件系统 API |',
'| `routes/api_flash_execute.py` | 后端步骤执行 API |',
    ].join('\n');

    /** 打开指南预览弹窗 */
    function openGuideModal() {
        var modal = document.getElementById('pmGuideModal');
        var content = document.getElementById('pmGuideContent');
        if (!modal || !content) return;
        content.innerHTML = renderMarkdown(GUIDE_CONTENT);
        modal.style.display = 'flex';
    }

    /** 关闭指南预览弹窗 */
    function closeGuideModal() {
        var modal = document.getElementById('pmGuideModal');
        if (modal) modal.style.display = 'none';
    }

    /** 复制指南全文到剪贴板 */
    function copyGuide() {
        var text = GUIDE_CONTENT;
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(function() {
                if (typeof showToast === 'function') showToast('已复制到剪贴板');
            }).catch(function() {
                _fallbackCopy(text);
            });
        } else {
            _fallbackCopy(text);
        }
    }

    function _fallbackCopy(text) {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); if (typeof showToast === 'function') showToast('已复制到剪贴板'); } catch(e) {}
        document.body.removeChild(ta);
    }

    /** 下载指南为 .md 文件 */
    function downloadGuide() {
        var blob = new Blob([GUIDE_CONTENT], { type: 'text/markdown;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = '解析器开发指南.md';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(function() { URL.revokeObjectURL(url); }, 100);
        if (typeof showToast === 'function') showToast('已导出 解析器开发指南.md');
    }

    /** 极简 Markdown 渲染 */
    function renderMarkdown(md) {
        var html = escHtml(md);
        // 代码块 ```
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function(m, lang, code) {
            return '<pre style="background:var(--card-bg,#1c1c1e);border:1px solid var(--rule);border-radius:8px;padding:10px;overflow-x:auto;font-size:12px;margin:8px 0;"><code>' + code + '</code></pre>';
        });
        // 行内代码
        html = html.replace(/`([^`]+)`/g, '<code style="background:var(--card-bg,#1c1c1e);padding:1px 4px;border-radius:3px;font-size:12px;">$1</code>');
        // 标题
        html = html.replace(/^### (.+)$/gm, '<h4 style="margin:14px 0 6px;font-size:14px;">$1</h4>');
        html = html.replace(/^## (.+)$/gm, '<h3 style="margin:16px 0 8px;font-size:16px;">$1</h3>');
        html = html.replace(/^# (.+)$/gm, '<h2 style="margin:18px 0 10px;font-size:18px;">$1</h2>');
        // 表格
        html = html.replace(/^\|(.+)\|$/gm, function(m, content) {
            var cells = content.split('|').map(function(c) { return c.trim(); });
            if (cells[0] === '---' || /^-+$/.test(cells[0])) return ''; // 分隔行
            if (cells.every(function(c) { return /^-+$/.test(c); })) return ''; // 分隔行
            var tag = 'td';
            return '<tr>' + cells.map(function(c) { return '<' + tag + ' style="padding:4px 8px;border:1px solid var(--rule);">' + c + '</' + tag + '>'; }).join('') + '</tr>';
        });
        // 表格包裹
        html = html.replace(/(<tr>[\s\S]*?<\/tr>\n?)+/g, function(m) {
            return '<table style="border-collapse:collapse;width:100%;font-size:12px;margin:8px 0;">' + m + '</table>';
        });
        // 有序列表
        html = html.replace(/^\d+\. (.+)$/gm, '<li style="margin-left:20px;list-style:decimal;">$1</li>');
        // 无序列表
        html = html.replace(/^[-*] (.+)$/gm, '<li style="margin-left:20px;list-style:disc;">$1</li>');
        // 段落（连续空行分段）
        html = html.replace(/\n\n/g, '</p><p style="margin:6px 0;">');
        html = '<p style="margin:6px 0;">' + html + '</p>';
        return html;
    }

    /** 从 localStorage 读取 WebDAV 配置，返回后端 API 格式 */
    function getWebdavConfig() {
        var url = WD_DEFAULTS.url, user = WD_DEFAULTS.user, pass = WD_DEFAULTS.pass;
        try {
            var saved = localStorage.getItem('webdav_config');
            if (saved) {
                var cfg = JSON.parse(saved);
                if (cfg.url) { url = cfg.url; user = cfg.user || ''; pass = cfg.pass || ''; }
            }
        } catch(e) {}
        return { webdav_url: url, webdav_user: user, webdav_pass: pass };
    }

    /** 保存 WebDAV 配置到 localStorage */
    function saveWebdavConfig(url, user, pass) {
        try {
            localStorage.setItem('webdav_config', JSON.stringify({ url: url, user: user, pass: pass }));
        } catch(e) {}
    }

    /** 更新 WebDAV 配置状态显示 */
    function updateWebdavConfigStatus() {
        var cfg = getWebdavConfig();
        var statusEl = document.getElementById('pmWdConfigStatus');
        if (statusEl) {
            statusEl.textContent = '已配置: ' + (cfg.webdav_url || '');
            statusEl.style.color = 'var(--accent-green)';
        }
    }

    /** 打开 WebDAV 配置弹窗 */
    function openWebdavConfig() {
        var modal = document.getElementById('wdConfigModal');
        if (!modal) return;
        var cfg = getWebdavConfig();
        document.getElementById('wdCfgUrl').value = cfg.webdav_url || '';
        document.getElementById('wdCfgUser').value = cfg.webdav_user || '';
        document.getElementById('wdCfgPass').value = cfg.webdav_pass || '';
        modal.style.display = 'flex';
    }

    /** 关闭 WebDAV 配置弹窗 */
    function closeWebdavConfig() {
        var modal = document.getElementById('wdConfigModal');
        if (modal) modal.style.display = 'none';
    }

    /** 确认保存 WebDAV 配置 */
    function confirmWebdavConfig() {
        var url = document.getElementById('wdCfgUrl').value.trim();
        var user = document.getElementById('wdCfgUser').value.trim();
        var pass = document.getElementById('wdCfgPass').value.trim();
        if (!url) {
            if (typeof showToast === 'function') showToast('请输入 WebDAV 地址');
            return;
        }
        saveWebdavConfig(url, user, pass);
        updateWebdavConfigStatus();
        closeWebdavConfig();
        if (typeof showToast === 'function') showToast('WebDAV 配置已保存');
    }

    function init() {
        var modal = document.getElementById('parserMgrModal');
        var openBtn = document.getElementById('parserMgrBtn');
        var closeBtn = document.getElementById('pmCloseBtn');

        if (!modal || !openBtn) return;

        // 打开弹窗
        openBtn.addEventListener('click', function() {
            modal.style.display = 'flex';
            refreshInstalledList();
        });

        // 关闭弹窗
        closeBtn.addEventListener('click', function() { modal.style.display = 'none'; });
        var closeXBtn = document.getElementById('pmCloseXBtn');
        if (closeXBtn) closeXBtn.addEventListener('click', function() { modal.style.display = 'none'; });
        modal.addEventListener('click', function(e) { if (e.target === modal) modal.style.display = 'none'; });

        // Tab 切换
        document.querySelectorAll('.pm-tab').forEach(function(tab) {
            tab.addEventListener('click', function() {
                document.querySelectorAll('.pm-tab').forEach(function(t) { t.classList.remove('active'); });
                tab.classList.add('active');
                var target = tab.getAttribute('data-pm-tab');
                document.querySelectorAll('.pm-panel').forEach(function(p) { p.style.display = 'none'; });
                var panel = document.getElementById('pmPanel' + target.charAt(0).toUpperCase() + target.slice(1));
                if (panel) panel.style.display = 'block';
                if (target === 'list') refreshInstalledList();
            });
        });

        // --- 本地安装 ---
        var localPick = document.getElementById('pmLocalPickBtn');
        var localInstall = document.getElementById('pmLocalInstallBtn');
        var localName = document.getElementById('pmLocalFileName');
        var localStatus = document.getElementById('pmLocalStatus');
        var _pickedParserFile = null;

        if (localPick) {
            localPick.addEventListener('click', async function() {
                try {
                    // 优先使用前端文件管理器（后端模式）
                    if (typeof FileApi !== 'undefined' && typeof FilePicker !== 'undefined' && FilePicker.pick) {
                        var result = await FilePicker.pick({ mode: 'file', filter: '.js' });
                        if (result && result.path) {
                            // 通过后端读取文件内容，构造 File 对象
                            var resp = await fetch('/api/fs/read-abs?path=' + encodeURIComponent(result.path));
                            var data = await resp.json();
                            if (!data.success) { localStatus.textContent = '读取失败: ' + (data.error || ''); localStatus.style.color = 'var(--accent-red)'; return; }
                            var blob = new Blob([data.content], { type: 'text/javascript' });
                            _pickedParserFile = new File([blob], result.name, { type: 'text/javascript' });
                            localName.textContent = result.name;
                            localInstall.disabled = false;
                            localStatus.textContent = '';
                        }
                    } else {
                        // 降级：浏览器原生选择器
                        var localFile = document.getElementById('pmLocalFile');
                        if (localFile) localFile.click();
                    }
                } catch (e) {
                    if (e.message !== '用户取消选择') {
                        localStatus.textContent = '选择失败: ' + e.message;
                        localStatus.style.color = 'var(--accent-red)';
                    }
                }
            });
            // 浏览器原生选择器降级
            var localFile = document.getElementById('pmLocalFile');
            if (localFile) {
                localFile.addEventListener('change', function() {
                    if (localFile.files.length) {
                        _pickedParserFile = localFile.files[0];
                        localName.textContent = _pickedParserFile.name;
                        localInstall.disabled = false;
                    }
                });
            }
        }
        if (localInstall) {
            localInstall.addEventListener('click', function() {
                if (!_pickedParserFile) return;
                localStatus.textContent = '安装中...';
                localStatus.style.color = 'var(--text-muted)';
                _installLocal(_pickedParserFile, localStatus);
            });
        }

        // --- 直链安装 ---
        var urlInstall = document.getElementById('pmUrlInstallBtn');
        var urlInput = document.getElementById('pmUrlInput');
        var urlStatus = document.getElementById('pmUrlStatus');
        if (urlInstall) {
            urlInstall.addEventListener('click', function() {
                var url = (urlInput || {}).value || '';
                if (!url.trim()) { urlStatus.textContent = '请输入 URL'; urlStatus.style.color = 'var(--accent-red)'; return; }
                urlStatus.textContent = '下载中...'; urlStatus.style.color = 'var(--text-muted)';
                ParserRunner.installFromUrl(url.trim()).then(function(data) {
                    urlStatus.textContent = data.success ? data.message : ('失败: ' + data.error);
                    urlStatus.style.color = data.success ? 'var(--accent-green)' : 'var(--accent-red)';
                    if (data.success) refreshInstalledList();
                }).catch(function(e) { urlStatus.textContent = '错误: ' + e.message; urlStatus.style.color = 'var(--accent-red)'; });
            });
        }

        // --- WebDAV 配置弹窗 ---
        var wdConfigBtn = document.getElementById('pmWdConfigBtn');
        if (wdConfigBtn) wdConfigBtn.addEventListener('click', openWebdavConfig);
        var wdCfgCloseBtn = document.getElementById('wdConfigCloseBtn');
        if (wdCfgCloseBtn) wdCfgCloseBtn.addEventListener('click', closeWebdavConfig);
        var wdCfgCancelBtn = document.getElementById('wdCfgCancelBtn');
        if (wdCfgCancelBtn) wdCfgCancelBtn.addEventListener('click', closeWebdavConfig);
        var wdCfgConfirmBtn = document.getElementById('wdCfgConfirmBtn');
        if (wdCfgConfirmBtn) wdCfgConfirmBtn.addEventListener('click', confirmWebdavConfig);
        var wdConfigModal = document.getElementById('wdConfigModal');
        if (wdConfigModal) wdConfigModal.addEventListener('click', function(e) { if (e.target === wdConfigModal) closeWebdavConfig(); });
        // 初始化配置状态显示
        updateWebdavConfigStatus();

        // --- WebDAV 安装 ---
        var wdRefresh = document.getElementById('pmWdRefreshBtn');
        var wdStatus = document.getElementById('pmWdStatus');
        if (wdRefresh) {
            wdRefresh.addEventListener('click', function() {
                wdStatus.textContent = '加载中...'; wdStatus.style.color = 'var(--text-muted)';
                var config = getWebdavConfig();
                if (!config.webdav_url) {
                    wdStatus.textContent = '请先配置 WebDAV';
                    wdStatus.style.color = 'var(--accent-red)';
                    return;
                }
                ParserRunner.webdavListParsers(config).then(function(data) {
                    if (!data.success) { wdStatus.textContent = '失败: ' + data.error; wdStatus.style.color = 'var(--accent-red)'; return; }
                    var list = data.files || [];
                    var container = document.getElementById('pmWdFileList');
                    if (!list.length) {
                        container.innerHTML = '<span style="color:var(--text-muted)">没有找到解析器</span>';
                        wdStatus.textContent = '没有找到解析器';
                        wdStatus.style.color = 'var(--text-muted)';
                        return;
                    }
                    container.innerHTML = list.map(function(f) {
                        return '<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid var(--rule)">' +
                            '<span>' + escHtml(f.name) + '</span>' +
                            '<button class="btn secondary small" data-wd-install="' + escHtml(f.name) + '">安装</button>' +
                            '</div>';
                    }).join('');
                    wdStatus.textContent = '共找到 ' + list.length + ' 个解析器';
                    wdStatus.style.color = 'var(--accent-green)';
                    // 绑定安装按钮
                    container.querySelectorAll('[data-wd-install]').forEach(function(btn) {
                        btn.addEventListener('click', function() {
                            var fname = btn.getAttribute('data-wd-install');
                            wdStatus.textContent = '安装 ' + fname + '...'; wdStatus.style.color = 'var(--text-muted)';
                            ParserRunner.installFromWebdav(fname, config).then(function(data) {
                                wdStatus.textContent = data.success ? data.message : ('失败: ' + data.error);
                                wdStatus.style.color = data.success ? 'var(--accent-green)' : 'var(--accent-red)';
                                if (data.success) refreshInstalledList();
                            });
                        });
                    });
                }).catch(function(e) { wdStatus.textContent = '错误: ' + e.message; wdStatus.style.color = 'var(--accent-red)'; });
            });
        }

        // --- 覆盖确认 ---
        var owYes = document.getElementById('pmOverwriteYes');
        var owNo = document.getElementById('pmOverwriteNo');
        if (owYes) owYes.addEventListener('click', function() { _doOverwrite(true); });
        if (owNo) owNo.addEventListener('click', function() { _doOverwrite(false); });

        // --- 解析器开发指南 ---
        var guideReadBtn = document.getElementById('pmGuideReadBtn');
        var guideExportBtn = document.getElementById('pmGuideExportBtn');
        if (guideReadBtn) guideReadBtn.addEventListener('click', openGuideModal);
        if (guideExportBtn) guideExportBtn.addEventListener('click', downloadGuide);

        var guideCloseBtn = document.getElementById('pmGuideCloseBtn');
        if (guideCloseBtn) guideCloseBtn.addEventListener('click', closeGuideModal);
        var guideCopyBtn = document.getElementById('pmGuideCopyBtn');
        if (guideCopyBtn) guideCopyBtn.addEventListener('click', copyGuide);
        var guideDownloadBtn = document.getElementById('pmGuideDownloadBtn');
        if (guideDownloadBtn) guideDownloadBtn.addEventListener('click', downloadGuide);
        var guideModal = document.getElementById('pmGuideModal');
        if (guideModal) guideModal.addEventListener('click', function(e) { if (e.target === guideModal) closeGuideModal(); });
    }

    async function refreshInstalledList() {
        var container = document.getElementById('pmInstalledList');
        if (!container) return;
        try {
            var parsers = await ParserRunner.listParsers();
            if (!parsers.length) {
                container.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-muted)">暂无已安装的解析器</div>';
                return;
            }
            container.innerHTML = parsers.map(function(p) {
                return '<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--rule)">' +
                    '<div><strong>' + escHtml(p.name || p.filename) + '</strong>' +
                    '<br><span style="font-size:11px;color:var(--text-muted)">' + escHtml(p.filename) + ' · ' + (p.installed_at || '') + ' · ' + ((p.size||0)/1024).toFixed(1) + 'KB</span></div>' +
                    '<button class="btn secondary small" style="color:var(--accent-red)" data-uninstall="' + escHtml(p.filename) + '">卸载</button>' +
                    '</div>';
            }).join('');
            container.querySelectorAll('[data-uninstall]').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    var fname = btn.getAttribute('data-uninstall');
                    if (typeof showConfirm === 'function') {
                        showConfirm('确认卸载', '确定要卸载解析器 ' + fname + ' 吗？', function() {
                            ParserRunner.uninstallParser(fname).then(function(data) {
                                if (data.success) refreshInstalledList();
                            });
                        });
                    } else if (confirm('确定要卸载解析器 ' + fname + ' 吗？')) {
                        ParserRunner.uninstallParser(fname).then(function(data) {
                            if (data.success) refreshInstalledList();
                        });
                    }
                });
            });
        } catch (e) {
            container.innerHTML = '<span style="color:var(--accent-red)">加载失败: ' + escHtml(e.message) + '</span>';
        }
    }

    async function _installLocal(file, statusEl) {
        var formData = new FormData();
        formData.append('file', file);
        try {
            var data = await ParserRunner.installParser(formData);
            if (data.success) {
                statusEl.textContent = data.message;
                statusEl.style.color = 'var(--accent-green)';
                refreshInstalledList();
            } else if (data.error === 'overwrite_confirm') {
                // 需要覆盖确认
                _pendingOverwrite = { file: file, statusEl: statusEl };
                var owConfirm = document.getElementById('pmOverwriteConfirm');
                var owMsg = document.getElementById('pmOverwriteMsg');
                owMsg.textContent = data.message;
                owConfirm.style.display = 'block';
                statusEl.textContent = '等待确认覆盖...';
                statusEl.style.color = 'var(--accent-orange)';
            } else {
                statusEl.textContent = '失败: ' + data.error;
                statusEl.style.color = 'var(--accent-red)';
            }
        } catch (e) {
            statusEl.textContent = '错误: ' + e.message;
            statusEl.style.color = 'var(--accent-red)';
        }
    }

    async function _doOverwrite(confirmed) {
        var owConfirm = document.getElementById('pmOverwriteConfirm');
        owConfirm.style.display = 'none';
        if (!confirmed || !_pendingOverwrite) { _pendingOverwrite = null; return; }
        var info = _pendingOverwrite;
        _pendingOverwrite = null;
        info.statusEl.textContent = '覆盖安装中...';
        info.statusEl.style.color = 'var(--text-muted)';
        // 带 force=true 重新上传
        var formData = new FormData();
        formData.append('file', info.file);
        formData.append('force', 'true');
        try {
            var data = await ParserRunner.installParser(formData);
            info.statusEl.textContent = data.success ? data.message : ('失败: ' + data.error);
            info.statusEl.style.color = data.success ? 'var(--accent-green)' : 'var(--accent-red)';
            if (data.success) refreshInstalledList();
        } catch (e) {
            info.statusEl.textContent = '错误: ' + e.message;
            info.statusEl.style.color = 'var(--accent-red)';
        }
    }

    // 注册模块
    if (typeof Modules !== 'undefined' && Modules.register) {
        Modules.register('parser-manager', ['parser-runner'], init);
    }
})();
