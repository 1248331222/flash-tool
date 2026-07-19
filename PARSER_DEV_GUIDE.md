# 天树刷机 — 解析器开发指南

解析器是一个独立的 JS 模块，负责将刷机脚本转换为后端可执行的步骤列表。本文档只规定两件事：我们给你什么，你必须返回什么。解析器内部如何处理脚本，完全由开发者自行决定。

## 匹配机制

解析器文件名必须与分类器产出的特征键精确匹配，格式为 `特征键.js`。分类器扫描脚本语法特征并组合成键，如 `bat_for_if_percent`，对应的解析器文件名就是 `bat_for_if_percent.js`。匹配失败时系统提示用户安装对应解析器，不做降级。

### BAT 脚本特征

| 类别 | 变体 | 匹配规则 |
|------|------|----------|
| loop | `for` / `for_f` / `nested_for` | `for %%X in (` / `for /f` / 2 个以上 for 循环 |
| condition | `if` | 任何 `if` 语句 |
| branch | `goto` / `call` / `interactive` | `goto :label` 或 `goto label` / `call :` / `set /p` 或 `choice /` |
| variable | `percent` / `delayed` | `%VAR%` 或 `%~dp0` / `!VAR!` |
| tool_ref | `direct` / `indirect` / `prefixed` | 行首直接调用 `fastboot`/`adb` / `%...TOOL/PATH...%` / `"fastboot.exe"` |

### SH 脚本特征

| 类别 | 变体 | 匹配规则 |
|------|------|----------|
| loop | `for` / `cfor` / `while` | `for X in` / `for ((` / `while` |
| condition | `if` / `case` | `if [` / `case X in` |
| function_def | `defined` | `function X` 或 `X()` + `{` |
| expansion | `dollar_sub` / `backtick` / `dollar_brace` | `$( )` / `` ` ` `` / `${ }` |
| structure | `pipe` / `redirect` | `\|` / `<` `>` |
| path_util | `dirname` | `dirname` / `readlink` / `pwd` / `realpath` |

特征键格式为 `脚本类型_变体1_变体2_...`，`none` 变体跳过，按类别定义顺序排列。例如包含 `for` 循环、`if` 条件、`%VAR%` 变量的 BAT 脚本，特征键为 `bat_for_if_percent`。

一个只包含 `fastboot flash boot boot.img` 和 `fastboot reboot` 的简单 BAT 脚本，特征键为 `bat_direct`，对应解析器文件名 `bat_direct.js`。

分类器还会检测参数占位符（BAT 的 `%*` `%1`-`%9`，SH 的 `$@` `$1`-`$9`），检测到时前端会显示参数输入框，用户填写的值通过 `ctx.extraArgs` 传入解析器。

## 我们提供的接口

### 调用签名

系统通过 `import()` 加载解析器模块，调用其导出的 `parse` 函数：

```javascript
parse(content, ctx)
```

- `content`：`string`，脚本完整文本
- `ctx`：`object`，上下文对象，见下表

解析器可以使用 `export function parse` 或 `export default function parse` 导出。CommonJS 格式（`module.exports = { parse: function... }`）也支持，系统会自动转换。

### 上下文对象 ctx

| 字段 | 类型 | 说明 |
|------|------|------|
| `fileApi` | object | 文件系统 API 实例，详见下文 |
| `extraArgs` | string | 用户填写的脚本参数，可能为空字符串 |
| `romDir` | string | 脚本所在目录的绝对路径 |
| `scriptPath` | string | 脚本文件的绝对路径 |

### 路径可用性

后端模式下，用户通过内置文件管理器选择脚本文件。文件管理器浏览整个手机文件系统，选择文件后系统获得脚本的绝对路径，并自动计算 `romDir`（脚本所在目录）。因此：

| 场景 | romDir / scriptPath | fileApi |
|------|---------------------|---------|
| 后端模式 + 文件管理器选择 | 有值（绝对路径） | 全部可用 |
| 后端模式 + 浏览器选择器 | 空字符串 | 全部可用 |
| WebUSB 模式 | 空字符串 | 不可用（返回空值） |

`ctx.scriptPath` 是脚本文件的绝对路径（如 `/sdcard/rom/flash.bat`），`ctx.romDir` 是脚本所在目录（如 `/sdcard/rom`）。解析器用 `ctx.romDir` 拼接脚本中的相对路径（如 `boot.img` → `/sdcard/rom/boot.img`）。

### FileApi 接口

解析器通过 `ctx.fileApi` 访问后端文件系统。后端模式下全部可用；WebUSB 模式下不可用，调用返回空值或 false。

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `list` | `list(dirPath, pattern?)` | `Promise<{name, path, type, size}[]>` | 列出目录内容 |
| `exists` | `exists(filePath)` | `Promise<boolean>` | 检查文件或目录是否存在 |
| `glob` | `glob(pattern, basePath)` | `Promise<string[]>` | 展开通配符，返回匹配文件的绝对路径列表 |
| `read` | `read(filePath, encoding?)` | `Promise<string>` | 读取文本文件，自动检测编码（utf-8/gbk/gb2312） |
| `readWithMeta` | `readWithMeta(filePath, encoding?)` | `Promise<{content, abs_path}>` | 读取文件并返回绝对路径 |
| `readBinary` | `readBinary(filePath)` | `Promise<Uint8Array>` | 读取二进制文件 |
| `mkdir` | `mkdir(dirPath)` | `Promise<void>` | 创建目录（递归） |
| `remove` | `remove(filePath)` | `Promise<void>` | 删除文件或目录 |
| `copy` | `copy(src, dst)` | `Promise<void>` | 复制文件或目录 |
| `move` | `move(src, dst)` | `Promise<void>` | 移动文件或目录 |

## 解析器必须返回的内容

解析器的返回值会被步骤列表和后端执行器读取。支持以下四种返回形式，选择哪一种由开发者根据需要决定。

### 形式一：步骤数组

直接返回步骤对象数组。

```javascript
export function parse(content, ctx) {
    return [
        { type: 'flash', partition: 'boot', imagePath: '/sdcard/boot.img', raw: 'fastboot flash boot /sdcard/boot.img', risk: 'MEDIUM' },
        { type: 'reboot', target: 'system', raw: 'fastboot reboot', risk: 'LOW' },
    ];
}
```

### 形式二：带元信息的对象

返回包含 `steps` 数组的对象，可附加参数提示信息。

```javascript
export function parse(content, ctx) {
    return {
        steps: [ /* 步骤对象 */ ],
        hasScriptParams: true,
        scriptParamHint: '请输入序列号',
    };
}
```

### 形式三：Promise

返回 Promise，resolve 为步骤数组或带元信息的对象。

```javascript
export async function parse(content, ctx) {
    const files = await ctx.fileApi.glob('*.img', ctx.romDir);
    return files.map(f => ({
        type: 'flash',
        partition: f.split('/').pop().replace('.img', ''),
        imagePath: f,
        raw: `fastboot flash ${f.split('/').pop().replace('.img', '')} ${f}`,
        risk: 'MEDIUM',
    }));
}
```

### 形式四：Async Generator

需要交互式解析时（如脚本含 `set /p` 用户输入），返回 async generator，逐步 `yield` 步骤或交互请求。

```javascript
export async function* parse(content, ctx) {
    yield { type: 'step', step: { type: 'flash', partition: 'boot', imagePath: '/path/boot.img', raw: 'fastboot flash boot /path/boot.img', risk: 'MEDIUM' } };

    const userChoice = yield { type: 'choice', prompt: '请选择刷写方式', options: ['全部刷写', '仅 boot'] };

    if (userChoice === 0) {
        yield { type: 'step', step: { type: 'flash', partition: 'system', imagePath: '/path/system.img', raw: 'fastboot flash system /path/system.img', risk: 'MEDIUM' } };
    }
}
```

generator yield 值的格式：

| yield 值 | 含义 |
|----------|------|
| `{ type: 'step', step: { 步骤对象 } }` | 追加一个步骤到列表 |
| `{ type: 'choice', prompt: string, options: string[] }` | 暂停，弹出选择框，用户选择后返回索引（0-based） |
| `{ type: 'confirm', prompt: string }` | 暂停，弹出确认框 |

如果 yield 的值没有 `type` 字段，或 `type` 不是 `choice`/`confirm`，系统将其视为步骤对象直接追加。

#### ⚠️ Generator 模式关键规则（易错点）

**1. `yield` 只能出现在 `async function*` 中（带星号）**

`async function` 和 `async function*` 是不同的。普通 `async function` 中使用 `yield` 会报 `Unexpected strict mode reserved word` 语法错误。

```javascript
// ❌ 错误：async function（无星号）中使用 yield
async function executeLine(line) {
    var step = makeStep(line);
    if (step) yield { type: 'step', step: step };  // 语法错误！
}

// ✅ 正确：async function*（带星号）中使用 yield
async function* executeLine(line) {
    var step = makeStep(line);
    if (step) yield { type: 'step', step: step };
}
```

**2. 调用含 `yield` 的函数必须用 `yield*` 委托，不能用 `await`**

`await` 只能等待 Promise 的结果，无法传递 yield 值。必须用 `yield*` 将内层 generator 的 yield 值向上传递。

```javascript
// ❌ 错误：用 await 调用 generator 函数，yield 值会丢失
async function* processLines(lines) {
    await executeLine(line);  // executeLine 中的 yield 无法传递到顶层！
}

// ✅ 正确：用 yield* 委托，yield 值逐层向上传递
async function* processLines(lines) {
    yield* executeLine(line);  // executeLine 的 yield 传递到 processLines → 顶层
}
```

**3. 不使用 yield 的辅助函数保持普通 `async function` 即可**

```javascript
// 这个函数不 yield，用普通 async function + await 即可
async function expandCollection(pattern) {
    var files = await ctx.fileApi.glob(pattern, dir);
    return files;
}

// 调用处用 await
var items = await expandCollection(col);
```

**4. 完整模式：内层函数 yield → yield* 委托 → 顶层 generator**

```javascript
export async function* parse(content, ctx) {
    // 顶层 yield choice
    var choice = yield { type: 'choice', prompt: '...', options: ['Y', 'N'] };

    // 委托给内层 generator
    yield* processLines(lines);
}

// 内层也必须是 async function*
async function* processLines(lines) {
    for (var line of lines) {
        yield* executeLine(line);  // 继续委托
    }
}

// 最内层也必须是 async function*
async function* executeLine(line) {
    var step = makeStep(line);
    if (step) {
        yield { type: 'step', step: step };  // 最终的 yield
    }
}

// 不 yield 的函数保持普通 async function
async function expandCollection(pattern) {
    return await ctx.fileApi.glob(pattern, dir);
}
```

**速查表：**

| 函数内是否使用 yield | 函数声明 | 调用方式 |
|---|---|---|
| 是 | `async function*` | `yield* fn()` |
| 否 | `async function` | `await fn()` |

## 步骤对象格式

每个步骤对象描述一条后端要执行的命令。

### 字段定义

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | 是 | 步骤类型，见下表 |
| `partition` | string | 视类型 | 目标分区名 |
| `imagePath` | string | 视类型 | 镜像文件绝对路径 |
| `raw` | string | 否 | 完整命令文本，提供时后端优先使用 |
| `risk` | string | 否 | 风险等级，默认 `MEDIUM`（仅用于内部记录，前端步骤列表不显示风险标签） |
| `params` | string | 否 | 附加参数 |
| `target` | string | 否 | 重启目标 |
| `prefixParams` | string | 否 | 前缀参数，放在 `flash` 命令之前（如 `--disable-verity`） |
| `condition` | string | 否 | 条件表达式，满足时才执行该步骤 |

### 步骤类型

| type | 用途 | 需要的字段 | 示例 raw |
|------|------|-----------|----------|
| `flash` | 刷写分区 | partition, imagePath | `fastboot flash boot /path/boot.img` |
| `erase` | 擦除分区 | partition | `fastboot erase userdata` |
| `reboot` | 重启 | target | `fastboot reboot bootloader` |
| `set_active` | 设置活动槽位 | partition (`a`/`b`) | `fastboot --set-active=a` |
| `getvar` | 查询变量 | raw | `fastboot getvar all` |
| `oem` | OEM 命令 | raw | `fastboot oem unlock` |
| `flashing` | flashing 子命令 | raw | `fastboot flashing unlock` |
| `shell` | ADB shell | raw | `adb shell pm list packages` |
| `raw` | 原始命令 | raw | 任意 fastboot/adb 命令 |
| `wait_reconnect` | 等待设备重连 | target (`bootloader`/`fastboot`) | — |
| `decompress` | 解压文件 | format, inputFile, outputFile | `zstd -d super.zst -o super.img` |

### decompress 类型

当脚本包含 `zstd.exe`、`7z`、`unzip` 等解压命令时，解析器应返回 `decompress` 类型步骤。后端会自动在设备上执行解压。

```javascript
{
    type: 'decompress',
    format: 'zstd',           // 压缩格式：zstd / 7z / zip
    inputFile: '/path/super.zst',   // 压缩文件路径
    outputFile: '/path/super.img',  // 输出文件路径（zstd 无 -o 时可省略，自动去掉 .zst）
    removeSource: true,       // 是否删除源文件（对应 zstd --rm）
    raw: 'zstd --rm -d super.zst -o super.img',
    risk: 'LOW'
}
```

后端执行策略：
- **zstd**：优先使用 `zstd` 命令行工具，回退到 Python `zstandard` 库
- **7z/zip**：优先使用 `7z`/`7za`/`7zr`，zip 格式优先 `unzip`
- 未安装对应工具时返回错误并提示安装命令

### wait_reconnect 类型

当脚本执行中需要设备重启并等待重新连接时，使用 `wait_reconnect` 类型。前端会显示带 🔄 图标的特殊样式，执行时后端会等待设备重新出现在指定模式后再继续。

```javascript
{ type: 'wait_reconnect', target: 'bootloader', raw: 'wait for device reconnect', risk: 'LOW' }
```

### 风险等级

风险等级仅在内部记录和工作台风险评估中使用，前端步骤列表不再显示风险标签。

| 值 | 含义 |
|------|------|
| `CRITICAL` | 极高（如刷写 xbl/preloader） |
| `HIGH` | 高（如擦除 userdata） |
| `MEDIUM` | 中（默认，如刷写 boot） |
| `LOW` | 低（如重启命令） |

### 路径要求

`imagePath` 应为绝对路径。刷机脚本中给出的镜像路径通常是相对路径（如 `boot.img`），解析器必须使用 `ctx.romDir` 将其拼接为绝对路径。后端不会对路径做额外拼接。

当 `ctx.romDir` 为空时（WebUSB 模式或浏览器选择器），解析器无法生成绝对路径，保留相对路径即可——后端执行时会报文件不存在的错误，用户可手动修正。

### 参数占位符处理（%* / %1-%9）

当脚本包含 `%*`（BAT 表示所有命令行参数）或 `%1`-`%9`（第 N 个参数）时，系统采用**前端实时同步**机制：

#### 处理流程

1. **分类器检测**：扫描脚本文本，检测到 `%*` 或 `%1`-`%9` 时设置 `hasParams = true`
2. **前端显示参数输入框**：用户可在解析前或解析后随时填写参数
3. **解析器返回步骤**：解析器**应保留 `%*` 占位符在 `raw` 字段中**，不要自行替换
4. **前端实时同步**：解析完成后，前端检测步骤 `raw` 中的占位符：
   - 参数为空时：**移除** `%*` 和 `%1`-`%9`，清理多余空格（如 `fastboot %* -w` → `fastboot -w`）
   - 参数非空时：`%*` 替换为完整参数值，`%1`-`%9` 替换为按空格分割后的对应位置参数
   - 用户修改参数输入框时，**实时同步**到所有包含占位符的步骤，无需重新解析
5. **后端兜底**：执行阶段后端也会做相同的替换，确保万无一失

#### 解析器应该怎么做

**推荐做法：保留占位符，不要自行替换。**

```javascript
// ✅ 推荐：保留 %* 在 raw 中，让前端处理
var raw = 'fastboot ' + '%*' + ' -w';  // raw = "fastboot %* -w"
steps.push({ type: 'raw', raw: raw, risk: 'LOW' });
```

```javascript
// ❌ 不推荐：解析器自行替换（前端无法实时同步）
var raw = 'fastboot ' + (ctx.extraArgs || '') + ' -w';
steps.push({ type: 'raw', raw: raw, risk: 'LOW' });
```

保留占位符的好处：
- 用户修改参数时，步骤列表**实时更新**，无需重新解析
- 参数为空时，占位符被自动移除，不会出现在最终命令中
- 解析器逻辑更简单，不需要关心参数替换细节

#### 参数替换规则

| 占位符 | 替换规则 | 示例（extraArgs = "--skip-secondary -w"） |
|--------|----------|------------------------------------------|
| `%*` | 替换为完整的 extraArgs | `fastboot %* flash boot` → `fastboot --skip-secondary -w flash boot` |
| `%1` | 替换为第 1 个参数 | `fastboot %1` → `fastboot --skip-secondary` |
| `%2` | 替换为第 2 个参数 | `fastboot %2` → `fastboot -w` |
| `%3`-`%9` | 替换为对应位置参数（无则移除） | `fastboot %3` → `fastboot` |

当 extraArgs 为空时，所有占位符被移除，多余空格被清理。

### 参数位置（prefixParams）

对于 `flash` 类型的步骤，`prefixParams` 字段指定的参数会放在 `flash` 命令之前。后端构建命令的格式为：

```
fastboot [prefixParams] flash <partition> <imagePath> [params]
```

例如 `prefixParams: '--disable-verity --disable-verification'` 会生成：

```
fastboot --disable-verity --disable-verification flash vbmeta /path/vbmeta.img
```

这是谷歌官方标准写法，`--disable-verity` / `--disable-verification` 属于 `flash` 命令的全局刷写选项，规范上应放在 `flash` 之前。

## 最小示例解析器

以下是一个完整的最小可用解析器，对应特征键 `bat_direct`（包含直接调用 fastboot/adb 命令的 BAT 脚本）。它展示了如何获取脚本路径、如何使用 fileApi、如何返回步骤列表。

```javascript
// bat_direct.js
// 适配特征键: bat_direct
// 适配脚本: 直接调用 fastboot/adb 命令的 BAT 线刷脚本

export async function parse(content, ctx) {
    var steps = [];
    var romDir = ctx.romDir || '';

    // 逐行解析
    var lines = content.split('\n');
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();

        // 跳过注释和空行
        if (!line || line.startsWith('::') || line.startsWith('REM ')) continue;

        // 注意：不要替换 %* 和 %1-%9，保留在 raw 中让前端实时同步

        // fastboot flash <partition> <image>
        var flashMatch = line.match(/^fastboot\s+flash\s+(\S+)\s+(.+)/i);
        if (flashMatch) {
            var partition = flashMatch[1];
            var imagePath = flashMatch[2];

            // 相对路径用 romDir 拼接为绝对路径
            if (romDir && !imagePath.startsWith('/')) {
                imagePath = romDir + '/' + imagePath;
            }

            // 如果含通配符，用 fileApi 展开
            if (imagePath.indexOf('*') >= 0 || imagePath.indexOf('?') >= 0) {
                var dir = imagePath.substring(0, imagePath.lastIndexOf('/'));
                var pattern = imagePath.substring(imagePath.lastIndexOf('/') + 1);
                var files = await ctx.fileApi.glob(pattern, dir);
                if (files.length > 0) imagePath = files[0];
            }

            steps.push({
                type: 'flash',
                partition: partition,
                imagePath: imagePath,
                raw: 'fastboot flash ' + partition + ' ' + imagePath,
                risk: 'MEDIUM',
            });
            continue;
        }

        // fastboot erase <partition>
        var eraseMatch = line.match(/^fastboot\s+erase\s+(\S+)/i);
        if (eraseMatch) {
            steps.push({
                type: 'erase',
                partition: eraseMatch[1],
                raw: line,
                risk: 'HIGH',
            });
            continue;
        }

        // fastboot reboot [target]
        var rebootMatch = line.match(/^fastboot\s+reboot\s*(\S*)/i);
        if (rebootMatch) {
            steps.push({
                type: 'reboot',
                target: rebootMatch[1] || 'system',
                raw: line,
                risk: 'LOW',
            });
            continue;
        }

        // 其他 fastboot/adb 命令（含 %* 的命令也在此处理，保留占位符）
        if (/^(fastboot|adb)\s+/i.test(line)) {
            steps.push({ type: 'raw', raw: line, risk: 'MEDIUM' });
        }
    }

    return { steps: steps };
}
```

这个解析器做了三件关键的事：

1. **从 `ctx.romDir` 获取脚本目录**，用它与脚本中的相对路径（如 `boot.img`）拼接为绝对路径（如 `/sdcard/rom/boot.img`）
2. **调用 `ctx.fileApi.glob()` 展开通配符**，当脚本中出现 `*.img` 时通过后端文件系统 API 获取实际文件路径
3. **返回步骤数组**，每个步骤包含 `type`、`partition`、`imagePath`（绝对路径）、`raw`（完整命令）、`risk`

## 安装与管理

### 存储位置

解析器存储在后端 `~/.skytree/parsers/` 目录。每个解析器是一个 `.js` 文件。后端每次列出解析器时自动扫描目录，手动放入文件即可完成安装，删除文件即可卸载。

### 安装方式

前端"解析器管理"弹窗提供三种安装方式：本地文件上传、URL 直链下载、WebDAV 服务器浏览安装。同名解析器已存在时弹出覆盖确认。

WebDAV 安装支持配置弹窗，可保存 WebDAV 地址、用户名、密码到本地，下次使用时自动加载。默认配置指向坚果云 WebDAV 服务。

### 热插拔

安装和卸载不需要重启后端服务。已加载到内存的解析器有缓存，如需强制刷新可调用 `ParserRunner.clearCache()`。

## 调试

在浏览器控制台中可执行以下操作：

```javascript
// 查看脚本分类结果
ScriptClassifier.classify('脚本内容');

// 查看已安装解析器
ParserRunner.listParsers().then(parsers => console.table(parsers));

// 手动运行解析器
ParserRunner.run('bat_direct.js', '脚本内容', {
    fileApi: FileApi,
    extraArgs: '',
    romDir: '/sdcard/rom',
    scriptPath: '/sdcard/rom/flash.bat',
});
```

### 常见问题

| 问题 | 原因 |
|------|------|
| `没有导出 parse 函数` | 使用 `export function parse` 或 `module.exports = { parse: function... }` |
| `解析器 xxx 未安装` | 文件名与分类器输出的特征键不一致 |
| 步骤执行报路径错误 | `imagePath` 不是绝对路径，或 `ctx.romDir` 为空 |
| `fileApi` 方法返回空 | WebUSB 模式下后端不可用 |
| `解析器内部错误: module is not defined` | CommonJS 格式会被自动转换，但如果代码中混合使用 require 和 export 可能出错 |

## 相关文件

| 文件 | 角色 |
|------|------|
| `static/js/core/classifier.js` | 分类器 |
| `static/js/core/parser-runner.js` | 解析器加载与运行 |
| `static/js/core/file-api.js` | FileApi 封装 |
| `static/js/components/file-picker.js` | 前端文件管理器 |
| `static/js/components/batch-new.js` | 线刷页面 |
| `static/js/components/parser-manager.js` | 解析器管理弹窗 |
| `routes/api_parsers.py` | 后端解析器管理 API |
| `routes/api_fs.py` | 后端文件系统 API |
| `routes/api_flash_execute.py` | 后端步骤执行 API |
