# Flash Tool 前端架构说明

本文档描述 `static/js/` 目录下的代码组织方式、模块约定、状态流转以及 DOM 安全访问原则，用于指导后续维护与扩展。

## 1. 目录职责

```
static/js/
├── core/          # 基础设施：启动、状态、模块系统、安全 DOM、API、UI 公共函数
├── views/         # 页面级模块：与具体导航页面对应，负责页面内业务逻辑
└── components/    # 可复用组件/驱动：上传、WebUSB、交互选择器、风险分析等
```

### 1.1 `core/` —— 基础设施

| 文件 | 职责 |
|------|------|
| `safe-dom.js` | 安全 DOM 访问层。提供 `SafeDOM.get / getRaw / exists / ifExists` 及全局补丁，避免元素缺失导致空引用抛错。 |
| `module-system.js` | 轻量级模块注册与初始化系统。支持依赖声明、拓扑排序、异步初始化、单模块失败隔离。 |
| `state.js` | 集中式应用状态 `App`，含事件总线 `App.event`、状态订阅 `App.get/set/subscribe/dispatch`，并维护旧全局变量的双向同步别名。 |
| `api.js` | WebSocket 初始化、`ModuleTask` 任务封装、`apiRequest / apiGet / apiPost / parseApiResponse` 统一请求辅助。 |
| `ui.js` | 公共 UI 函数：进度条、模块状态、主题、日志、Toast、确认弹窗、全局 `data-action` 事件委托等。 |
| `init.js` | 应用初始化入口。DOMReady 后启动模块系统，完成导航绑定、视图恢复、数据预加载等。 |
| `config.js` | 集中配置常量（超时、轮询间隔等）。 |
| `utils.js` | 通用辅助函数（转义、填充下拉框等）。 |

### 1.2 `views/` —— 页面级模块

每个文件对应底部导航或主要功能区域，例如：

- `device.js` / `device_info.js`：设备检测与信息显示
- `bat.js`：线刷脚本解析与批量任务
- `flash.js` / `single.js`：单分区刷写
- `tools.js`：版本检查、更新、VBmeta 校验关闭
- `changelog.js`：版本页可折叠更新日志
- `workbench.js`：工作台自定义步骤
- `rom.js`：刷机包管理

页面模块通过 `Modules.register(name, deps, fn)` 注册，依赖 `core` 中提供的状态、API、UI 能力。

### 1.3 `components/` —— 可复用组件/驱动

| 文件 | 职责 |
|------|------|
| `webusb.js` | WebUSB Fastboot/ADB 设备连接与命令封装 |
| `upload.js` | 文件上传弹窗与提交逻辑 |
| `interactive_selector.js` | 交互式脚本分步选择器 |
| `bat_risk.js` | 线刷脚本风险分析与恢复卡片 |
| `toolbox_ops.js` | 工具箱快捷操作 |
| `custom_flash.js` | 自定义刷写相关逻辑 |

组件不直接对应页面，而是被多个 `views/` 或 `core/` 模块引用。

## 2. 模块注册约定

1. **注册方式**：所有 JS 文件均通过 IIFE 或顶层脚本加载，模块使用 `Modules.register(name, deps, fn)` 显式注册。
2. **命名规范**：
   - `core` 模块使用简短名词，如 `'state'`、`'ui'`、`'api'`。
   - `views` 模块使用页面名，如 `'tools'`、`'changelog'`。
   - 应用入口模块命名为 `'app-init'`。
3. **依赖声明**：`deps` 为字符串数组，表示执行前必须已初始化完成的模块。`fn` 的参数按 `deps` 顺序注入对应模块的返回值。
4. **执行顺序**：模块系统会在 `DOMContentLoaded` 后调用 `Modules.init()`，按拓扑排序执行；单个模块抛错不会影响其他模块。
5. **返回值**：初始化函数可返回任意对象/布尔值，供依赖模块使用；未显式返回时默认返回 `true`。
6. **DOM 查询时机**：初始化函数内再做 DOM 查询，避免脚本在 `<head>` 或页面元素尚未解析时执行。

### 2.1 事件委托约定

- 通用 `data-action` 点击事件由 `core/ui.js` 在 `document.body` 层统一委托处理。
- 组件如需处理自身特有的 `data-action`（如上传组件的 `view-uploaded-script`、`close-script-viewer`），**应在 `document.body` 上注册一次事件委托**，不要在子容器（如 `#uploadHistoryList`）上重复注册，否则同一点击会触发多次处理函数，导致弹窗打开两次等问题。
- 若子容器需要阻止冒泡，应显式调用 `e.stopPropagation()`，并注释说明原因。

## 3. 状态流

应用状态统一维护在全局 `App` 对象中（`state.js`）。

### 3.1 状态读写

- `App.get(key)` / `App.set(key, value)`：支持点分路径，如 `App.set('deviceInfo.product', 'xxx')`。
- `App.subscribe(key, fn)`：订阅指定状态变化，注册时立即以当前值触发一次回调；返回取消订阅函数。
- `App.dispatch(action)`：通过 `{ type, payload }` 批量更新状态，内置 `DEVICE_STATUS`、`RUN_MODE`、`STEP_LIST`、`BACKEND_READY`、`PROGRESS` 等标准动作。

### 3.2 事件总线

`App.event` 提供轻量级 pub/sub：

- `App.event.on(evt, fn)` / `off(evt, fn)` / `once(evt, fn)`
- `App.event.emit(evt, ...args)`

适用于一次性通知、跨模块广播等场景。

### 3.3 向后兼容别名

大量旧代码依赖 `window` 上的全局变量（如 `socket`、`stepList`、`deviceConnected`、`appRunMode` 等）。`state.js` 通过 `Object.defineProperty` 将这些全局变量双向同步到 `App`：

- 读取全局变量 → 从 `App[key]` 取值
- 写入全局变量 → 调用 `App.set(key, value)`

新代码应优先使用 `App.get/set/subscribe`。

## 4. DOM 安全访问原则

为避免“稍微改动 HTML 就崩溃”，项目采用以下安全策略：

1. **统一入口**：优先使用 `$(id)`（即 `SafeDOM.get`）查询元素，元素缺失时返回空代理，读写操作静默成功。
2. **原始查询**：需要判断元素是否真实存在时，使用 `SafeDOM.exists(id)` 或 `SafeDOM.getRaw(id)`。
3. **安全执行**：对可选元素执行一次性副作用时使用 `SafeDOM.ifExists(id, fn)`。
4. **全局补丁**：`safe-dom.js` 默认启用 `document.getElementById` 全局补丁，旧代码未使用 `$` 也能获得保护。
5. **避免链式空引用**：访问代理对象上的 `style`、`classList`、`dataset`、`children` 等常用属性不会抛错；方法调用返回安全默认值。
6. **缓存注意**：`SafeDOM.get` 会缓存元素引用；动态增删 DOM 后如需重新查询，可调用 `SafeDOM.clearCache()`。

## 5. 扩展建议

- 新增页面模块：在 `views/` 下新建文件，注册对应模块，并在 `init.js` 的预加载列表或导航事件中引用。
- 新增公共 UI 函数：优先放入 `ui.js`，并通过 `Modules.register('ui', ...)` 暴露或作为全局函数。
- 新增状态字段：在 `state.js` 的 `App` 对象中声明默认值，并视情况加入双向同步别名列表。
- 新增后端接口调用：优先使用 `apiGet / apiPost`，需要复杂流程时封装为 `ModuleTask` 子类或实例。

## 6. Web Component 组件演化（v3.9.0 更新）

项目正逐步从传统 `views/` + `index.html` 模式迁移到 Shadow DOM Web Component。当前已注册组件：

| 组件标签 | 对应文件 | 职责 |
|---|---|---|
| `<flash-panel>` | `components/flash-panel.js` | 线刷：ROM 选择→解压→解析→执行 |
| `<tools-panel>` | `components/tools-panel.js` | 工具箱：重启、VBmeta、AB槽位、双清、BL管理 |
| `<version-panel>` | `components/version-panel.js` | 版本信息与更新日志 |

### 6.1 组件与旧视图的共存规则

1. **不重复渲染**：组件挂载到独立容器（`#flashPanelContainer`、`#toolsPanelContainer`、`#versionPanel`），与旧 `views/` 模块互不冲突。
2. **后端地址同步**：通过 `SkytreeBus.on('backend:changed')` 监听地址变化，保持与旧系统的 backend URL 一致。
3. **事件隔离**：Shadow DOM（closed）自带样式/事件隔离，组件内部用 `this._shadow.getElementById()` 查询元素，不与旧 DOM 冲突。

### 6.2 `<tools-panel>` 组件核心操作

| # | 方法 | 说明 |
|---|---|---|
| 1 | `_updateVbmetaBtn()` | 根据输入框内容启用/禁用「执行关闭校验」按钮 |
| 2 | `_pickVbmetaImage()` | 调用 `/api/rom/projects` 获取已解压刷机包列表，弹窗让用户选择项目→自动查找 vbmeta.img 填入路径 |
| 3 | `_disableVbmeta()` | 调用 `/api/flash` 刷入 vbeatm 镜像并附加 `--disable-verity --disable-verification` 参数 |
| 4 | `_execCmd(tool, args)` | 通用命令执行（fastboot/adb） |
| 5 | `_execReboot(target)` | 重启到指定模式 |
| 6 | `_queryBl()` / `_execBl(action)` | Bootloader 锁状态查询/开锁/上锁 |
| 7 | `_execWipe()` | 双清（擦除 userdata + cache） |
| 8 | `_switchSlot()` | AB 槽位切换 |

### 6.3 `<flash-panel>` 组件核心操作

| # | 方法 | 说明 |
|---|---|---|
| 1 | `_parseScript()` | 解析脚本时附带 `extra_args`（来自 `#parseArgsInput` 输入框），传入后端 `/api/rom/parse` 的 `extra_args` 字段 |
| 2 | `_refreshRoms()` / `_extractRom()` | 刷新 ROM 列表 / 解压 |
| 3 | `_refreshProjects()` / `_refreshScripts()` | 刷新已解压项目 / 脚本列表 |
| 4 | `_executeFlash()` / `_simulateFlash()` | 执行/模拟线刷 |
| 5 | `_loadHistory()` | 加载刷机历史 |

### 6.4 参数输入框约定（`#parseArgsInput`）

- 位置：脚本选择行**下方**独占一行，`flex:1` 占满宽度
- 占位符：`"带参数解析默认无，如需请填写"`
- 空值时 API 调用不传 `extra_args` 字段
- 非空时传入 `{ project, script, extra_args: "用户输入的内容" }`
- 后端 `/api/rom/parse` 收到 `extra_args` 后将作为脚本 `%*` 或 `$@` 占位符展开

## 7. 版本号清单（v3.9.0）

修改以下位置可使版本号保持同步：

| 文件 | 行 | 示例 |
|---|---|---|
| `config.py` | `TOOL_VERSION = "3.9.0"` | 后端版本源 |
| `static/components/version-panel.js` | `_renderChangelog()` 内 logs 数组 | 组件版更新日志 |
| `static/js/views/changelog.js` | `CHANGELOG_TEXT` 顶部 | 旧版更新日志 |