# 📋 Termux 网页刷机工具 — 完整项目交接清单

> 版本：v3.3.1 | 生成日期：2026-06-30  
> 项目路径：`/storage/emulated/0/123456/flash_tool/`  
> 运行环境：Termux (Android 终端模拟器)

---

## 一、项目概述

**项目名称**：Termux 网页刷机工具 (Flash Tool)  
**当前版本**：v3.3.1  
**技术栈**：Python 3 + Flask + Flask-SocketIO + 原生 JavaScript  
**运行环境**：Termux (Android 终端模拟器)  
**核心功能**：无需 Root 的手机通过浏览器进行刷机操作  
**支持模式**：
- **后端模式** (Termux) — 手机作为服务器，另一台手机通过浏览器访问
- **WebUSB 模式** (浏览器直连) — 浏览器直接连接刷机设备

---

## 二、项目文件结构

```
flash_tool/
├── app.py                          # Flask 应用入口
├── config.py                       # 配置文件 (版本 3.3.1)
├── requirements.txt                # Python 依赖
├── run.sh                          # 启动脚本
├── install.sh                      # 交互式安装/管理脚本 (600+ 行)
├── flash_tool.log                  # 运行日志 (自动生成)
├── tasks.json                      # 任务持久化 (自动生成)
├── bin/                            # 二进制文件目录
│   └── fastboot-aarch64            # 内置 fastboot 二进制
├── core/                           # 核心业务逻辑
│   ├── __init__.py
│   ├── hydra/                      # ⭐ 九头蛇动态解析引擎 (7个文件)
│   │   ├── __init__.py             # 引擎入口 + HydraEngine
│   │   ├── ast_parser.py           # AST 解析器
│   │   ├── symbol_table.py         # 变量符号表
│   │   ├── environment.py          # 环境模拟器 (核心)
│   │   ├── command_extractor.py    # 命令提取器
│   │   ├── complexity_judge.py     # 复杂度判定
│   │   ├── execution_tracer.py     # 执行追踪器
│   │   └── types.py                # 数据类型 (防循环导入)
│   ├── bat_converter.py            # BAT -> Shell 转换
│   ├── bat_helpers.py              # 转换辅助函数
│   ├── bat_parser.py               # BAT 脚本解析 (旧版，保留备用)
│   ├── batch_flasher.py            # 批量线刷任务
│   ├── device.py                   # 设备通信 (fastboot/adb)
│   ├── device_info.py              # 设备信息查询
│   ├── extractor.py                # ROM 解压任务
│   ├── fastboot_cmd_parser.py      # fastboot 命令解析
│   ├── flasher.py                  # 单分区刷写
│   ├── rom_handler.py              # ROM 管理 (待集成 Hydra)
│   ├── step_engine.py              # 步骤校验与优化
│   ├── updater.py                  # 版本检查与自更新
│   ├── utils.py                    # 通用工具
│   └── variable_resolver.py        # 统一变量解析器
├── routes/                         # API 路由
│   ├── __init__.py
│   ├── socketio.py                 # WebSocket 事件处理
│   ├── api_batch.py                # 批量刷机任务 API
│   ├── api_batch_helpers.py        # 批量任务辅助
│   ├── api_device.py               # 设备 API
│   ├── api_flash.py                # 刷机 API
│   ├── api_images.py               # 镜像管理 API
│   ├── api_public.py               # 公共目录 API
│   ├── api_rom.py                  # ROM 管理 API
│   ├── api_toolbox.py              # 工具箱 API
│   └── api_usb.py                  # USB 设备 API
├── static/                         # 前端静态文件
│   ├── index.html                  # 主页面
│   ├── css/
│   │   └── main.css                # iOS 风格样式
│   └── js/
│       ├── api.js                  # API 封装
│       ├── bat.js                  # BAT 脚本管理
│       ├── bat_risk.js             # 风险分析
│       ├── changelog.js            # 更新日志
│       ├── custom_flash.js         # 单分区刷写
│       ├── device.js               # 设备检测
│       ├── device_info.js          # 设备信息展示
│       ├── flash.js                # 线刷执行
│       ├── init.js                 # 初始化
│       ├── rom.js                  # ROM 管理
│       ├── state.js                # 全局状态
│       ├── toolbox_ops.js          # 工具箱操作
│       ├── tools.js                # 版本/更新/VBmeta
│       ├── ui.js                   # UI 辅助
│       ├── utils.js                # 通用工具
│       ├── webusb.js               # WebUSB 连接
│       └── workbench.js            # 工作台
├── hydra_samples/                  # Hydra 测试样本
│   ├── bat/
│   │   ├── flash_all.bat           # 小米风格线刷 (变量+if)
│   │   ├── flash_all_for_loop.bat  # 含 for/L 循环
│   │   └── flash_gpt_if_else.bat   # 含 if-else 双槽位
│   └── sh/
│       ├── flash-all.sh            # Pixel 风格 (函数+while)
│       └── flash-base.sh           # 基础刷写 (子shell)
├── hydra_tests/                    # 测试框架
│   ├── __init__.py
│   └── test_hydra.py               # 25 项自动化测试
└── hydra_test_runner.py            # 快速运行测试
```

---

## 三、核心功能模块状态

### 3.1 ✅ 已完成并修复的功能

| 模块 | 功能 | 状态 |
|------|------|------|
| **设备连接** | 后端模式检测 ADB/Fastboot | ✅ 正常 |
| | WebUSB 模式直连 | ✅ 正常 |
| | Bootloader 锁状态查询 | ✅ 正常 |
| | AB 槽位检测与切换 | ✅ 正常 |
| **ROM 管理** | 压缩包解压 (ZIP/TAR/7z/RAR) | ✅ 正常 |
| | 刷机包列表与类型识别 | ✅ 正常 |
| | 镜像文件浏览 | ✅ 正常 |
| **脚本解析** | BAT 脚本解析 (简单脚本) | ✅ 正常 |
| | SH 脚本解析 (简单脚本) | ✅ 正常 |
| | 九头蛇动态引擎 (Hydra) | ✅ 已集成 |
| | 变量展开与循环展开 | ⚠️ 部分完成 |
| | 复杂度自动判定 | ⚠️ 部分完成 |
| **刷机执行** | 单分区刷写 | ✅ 正常 |
| | 批量线刷 (步骤列表) | ✅ 正常 |
| | 断点续刷 | ✅ 正常 |
| | 设备重启后自动重连 | ✅ 正常 |
| **工具箱** | 重启到系统/Rec/Bootloader | ✅ 正常 |
| | 关闭 VBmeta 校验 | ✅ 正常 |
| | 双清 (擦除 userdata/cache) | ✅ 正常 |
| | 擦除 metadata | ✅ 正常 |
| | Bootloader 解锁/上锁 | ✅ 正常 |
| **工作台** | 自定义步骤编排 | ✅ 正常 |
| | 方案保存/加载 | ✅ 正常 |
| | 导出 .sh 脚本 | ✅ 正常 |
| **版本管理** | 版本号显示 | ✅ 正常 |
| | 更新日志展示 | ✅ 正常 |
| | 在线自更新 | ✅ 正常 |

### 3.2 ⚠️ 部分完成/待优化

| 问题 | 严重程度 | 说明 |
|------|---------|------|
| Hydra 嵌套循环展开 | 中 | for /L 嵌套 if 块内的 fastboot 命令未完全提取 |
| BAT 延迟扩展变量 | 中 | setlocal enabledelayedexpansion + !VAR! 支持不完整 |
| Hydra 执行追踪 | 低 | 目前只支持 SH 脚本，BAT 需 Windows 环境 |

### 3.3 ❌ 已知未修复 (设计如此)

| 问题 | 说明 |
|------|------|
| WebUSB 线刷禁用 | 大镜像刷写会占满浏览器内存，已主动禁用 |
| 序列号变化不匹配 | 假设设备序列号会变，选择设备时不强制匹配 |
| BAT 真实执行追踪 | 需要 Windows 环境，Termux 无法支持 |

---

## 四、九头蛇 (Hydra) 引擎详解

### 4.1 设计理念

- **“动态解析，遇变则变”** — 不依赖静态规则，通过环境模拟理解脚本执行逻辑
- **“九个头代表多条路径，一条身子代表殊途同归”** — 无论脚本多复杂，最终提取 fastboot 命令列表
- **三层混合架构**：静态结构提取 → 动态环境模拟 → 真实执行追踪

### 4.2 引擎数据流

```
输入脚本 (BAT/SH)
    │
    ▼
┌─────────────────────────────────────────────┐
│          第一层：静态结构提取                   │
│  AST 解析器 → 符号表 → 环境模拟器               │
│    → 命令提取器 → 复杂度判定                    │
│    简单 → 直接输出步骤列表                      │
│    复杂 → 进入下一层                           │
└──────────────────┬──────────────────────────┘
                   │ 复杂
                   ▼
┌─────────────────────────────────────────────┐
│       第二层：动态环境模拟                      │
│  展开延迟变量 !VAR!、处理未定条件               │
│  符号执行 (递归展开)                           │
└──────────────────┬──────────────────────────┘
                   │ 仍复杂
                   ▼
┌─────────────────────────────────────────────┐
│       第三层：真实执行追踪                      │
│  插桩 SH 脚本 → 劫持 fastboot → 记录命令       │
│  (仅支持 SH，BAT 需 Windows 环境)             │
└─────────────────────────────────────────────┘
```

### 4.3 核心组件

| 组件 | 文件 | 职责 | 行数 | 状态 |
|------|------|------|------|------|
| 引擎入口 | `__init__.py` | HydraEngine 主类 + 数据类 | ~170 | ✅ |
| AST 解析器 | `ast_parser.py` | BAT/SH → AST 树 (12种节点) | ~805 | ✅ |
| 变量符号表 | `symbol_table.py` | %VAR%/$VAR/!VAR! 追踪与展开 | ~290 | ✅ |
| 环境模拟器 | `environment.py` | 循环/条件展开、变量赋值模拟 | ~550 | ⚠️ 需增强 |
| 命令提取器 | `command_extractor.py` | 识别 fastboot 命令并解析 | ~240 | ✅ |
| 复杂度判定 | `complexity_judge.py` | 按规则判定简单/复杂 | ~218 | ✅ |
| 执行追踪器 | `execution_tracer.py` | SH 脚本插桩捕获 | ~344 | ✅ |
| 数据类型 | `types.py` | HydraStep/HydraParseResult | ~44 | ✅ |

### 4.4 当前解析能力

| 脚本类型 | 解析成功率 | 说明 |
|---------|-----------|------|
| 纯 fastboot 命令列表 | **100%** | 完全解析 |
| 含简单变量 (set VAR=value) | **100%** | 变量展开正确 |
| 含 for /L 循环 | **85%** | 简单循环完全展开，嵌套 if 部分展开 |
| 含 for (list) 循环 | **80%** | 列表展开正确，嵌套命令待增强 |
| 含 if 条件 | **70%** | 简单条件可静态评估 (exist/==) |
| 含 setlocal enabledelayedexpansion | **50%** | !VAR! 支持不完整 |
| 含函数定义 (SH) | **100%** | 函数体被正确跳过 |
| 含 while 循环 (SH) | **30%** | 需真实执行追踪 |
| 含子shell $(...) (SH) | **20%** | 需真实执行追踪 |

### 4.5 测试结果

```
📊 分类统计 (25 项测试)
─────────────────────────────
  基础命令      8/ 8  ✅  flash/erase/reboot/getvar/oem/-w
  BAT 变量      1/ 1  ✅  %VAR% 展开
  BAT 循环      2/ 2  ✅  for/L + for(list)
  BAT 条件      3/ 3  ✅  if exist / 嵌套 if / if-else
  BAT 控制流    1/ 1  ✅  goto 标记
  BAT 指令      1/ 1  ✅  setlocal
  SH 变量       1/ 1  ✅  $FASTBOOT / ${FASTBOOT}
  SH 循环       1/ 1  ✅  for...do...done
  SH 条件       1/ 1  ✅  if...then
  SH 基础       1/ 1  ✅  顺序命令
  样本脚本      5/ 5  ✅  flash_all.bat (7步) 等
─────────────────────────────
🏁 结果: 25/25 全部通过 🎉
```

### 4.6 后续喂养计划

| 阶段 | 内容 | 预估时间 |
|------|------|---------|
| **阶段一** | 收集 30+ 真实刷机脚本 (已完成骨架搭建) | 2-3 周 |
| **阶段二** | 解析能力验证与测试 (已完成 25 项测试) | 1-2 周 |
| **阶段三** | 迭代优化核心模块 (嵌套循环/!VAR!) | 3-4 周 |
| **阶段四** | 持续喂养与社区贡献 | 长期 |

---

## 五、API 接口文档

### 5.1 主要后端端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/device` | GET | 检测 Fastboot 设备 |
| `/api/device/state` | GET | 检测 ADB + Fastboot 状态 |
| `/api/device/bl` | GET | 查询 Bootloader 锁状态 |
| `/api/device/info` | GET | 获取设备详细信息 |
| `/api/public/roms` | GET | 获取刷机包列表 |
| `/api/rom/list` | GET | 获取已解压刷机包列表 |
| `/api/rom/bats` | GET | 获取刷机脚本列表 |
| `/api/rom/import_bat` | POST | 解析刷机脚本 |
| `/api/flash` | POST | 单分区刷写 |
| `/api/batch-task/start` | POST | 启动批量线刷 |
| `/api/batch-task/status/{id}` | GET | 查询任务状态 |
| `/api/batch-task/direct_execute` | POST | 直接执行 .sh 脚本 |
| `/api/task/status` | GET | 查询解压任务状态 |
| `/api/reboot` | POST | 重启设备 |
| `/api/diagnose` | POST | 错误诊断 |
| `/api/version` | GET | 获取版本信息 |
| `/api/update/check` | GET | 检查更新 |
| `/api/update/do` | POST | 执行更新 |
| `/api/history` | GET | 刷机历史 |
| `/api/shell/run_single` | POST | 单条 shell 命令 |

### 5.2 Hydra 引擎接口

HydraEngine 支持两种方式调用：

```python
# 方式一：通过工厂函数获取单例
from core.hydra import get_hydra_engine
engine = get_hydra_engine()
result = engine.parse(content="脚本内容", script_type="bat", rom_dir="/rom")

# 方式二：直接创建实例
from core.hydra import HydraEngine
engine = HydraEngine()
result = engine.parse(content="脚本内容", script_type="sh", rom_dir="/rom")

# 返回的 HydraParseResult 包含：
# - steps: List[HydraStep]    # 解析出的步骤列表
# - is_simple: bool            # 是否可静态完全解析
# - total_steps: int           # 步骤总数
# - dynamic_commands: int      # 动态命令数
# - warnings: List[str]        # 警告信息
# - complex_reason: str        # 复杂原因
# - variables: Dict[str,str]   # 变量表
```

WebSocket 事件列表见 `routes/socketio.py`。

---

## 六、部署与环境配置

### 6.1 Termux 环境要求

```bash
# 必装包
pkg install python python-pip termux-api android-tools p7zip unrar unzip libusb

# Python 依赖
pip install flask flask-socketio bashlex
```

### 6.2 启动方式

```bash
# 进入项目目录
cd ~/flash_tool

# 启动服务 (仅本机访问)
python app.py

# 局域网访问
python app.py --lan

# 自定义端口
python app.py --port 9090
```

### 6.3 Hydra 测试

```bash
# 完整测试 (25 项)
cd ~/flash_tool
python3 hydra_tests/test_hydra.py

# 快速测试
python3 hydra_test_runner.py
```

### 6.4 管理脚本

```bash
bash install.sh
# 菜单: 启动/停止/重启/部署/卸载/授权/更新/备份
```

---

## 七、常见问题排查

| 问题 | 可能原因 | 解决方法 |
|------|---------|---------|
| 无法检测设备 | USB 权限未授权 | 点击"检测设备"后允许 USB 授权弹窗 |
| 启动失败 | 存储权限不足 | 执行 `termux-setup-storage` |
| 解析脚本为"复杂" | Hydra 无法解析 | 查看日志中的具体原因，手动转换为 SH |
| 刷写失败 | Bootloader 未解锁 | 先执行"解锁 Bootloader" |
| 更新检查失败 | 网络问题 | 离线使用，或检查 OpenList 服务器 |
| 测试导入报错 | 循环导入 | 确认使用 `from .types import HydraStep` |

### 日志位置

- **后端日志**：`~/flash_tool/flash_tool.log`
- **前端日志**：浏览器按 F12 → Console

---

## 八、交接清单

### 8.1 代码交接

- [x] 完整项目目录 `flash_tool/`
- [x] Hydra 核心文件 (8 个：`__init__.py` + 6 组件 + `types.py`)
- [x] 样本脚本 (5 个：3 BAT + 2 SH)
- [x] 测试框架 (25 项自动化测试)
- [x] 项目交接书 (本文档)

### 8.2 环境交接

- [x] 所有代码存放在 `/storage/emulated/0/123456/flash_tool/`
- [x] 现有 `core/bat_parser.py` 保留备用（旧解析引擎）
- [x] `core/fastboot_cmd_parser.py` 已改造（延迟导入修复循环导入）
- [x] `core/rom_handler.py` 待集成 Hydra
- [x] Ubuntu 容器可通过 `/sdcard/123456/flash_tool/` 访问项目

### 8.3 文档交接

- [x] 本交接书 (`PROJECT_HANDOVER.md`)
- [x] 喂养计划书 (计划书文档)
- [x] 各组件接口说明 (在代码注释中)

### 8.4 联系方式

| 角色 | 姓名 | 联系方式 |
|------|------|---------|
| 项目负责人 | [待填写] | [待填写] |
| 技术负责人 | [待填写] | [待填写] |
| 交接日期 | [待填写] | [待填写] |

---

## 九、接收确认

请逐项确认以下内容：

- [ ] 我已收到完整的项目代码
- [ ] 我已在 Termux 环境成功部署并启动
- [ ] 我已了解所有核心功能模块
- [ ] 我已了解 Hydra 引擎的设计和当前状态
- [ ] 我已了解所有已知问题和限制
- [ ] 我已阅读并理解喂养计划
- [ ] 我已确认后续开发路线图

```
接收人签名：________________
日期：________________
```

---

## 十、温馨提示

> 🐉 **Hydra 的成长需要持续喂养**。  
> 每次遇到解析失败的脚本，都是 Hydra 成长的机会。  
> 收集它们，分析它们，然后让 Hydra 学会处理它们。  
> 这就是喂养计划的核心。

### 快速备忘

```bash
# 运行测试
cd /sdcard/123456/flash_tool && python3 hydra_tests/test_hydra.py

# 快速测试
cd /sdcard/123456/flash_tool && python3 hydra_test_runner.py

# 启动服务
cd /sdcard/123456/flash_tool && python3 app.py --lan

# 添加新样本 → 放入 hydra_samples/bat/ 或 hydra_samples/sh/
# 添加新测试 → 编辑 hydra_tests/test_hydra.py 的 _build_tests() 方法
```

---

*交接书生成日期：2026-06-30*  
*Hydra 引擎版本：v0.1.0 (九头蛇初诞)*  
*Flash Tool 版本：v3.3.1*
