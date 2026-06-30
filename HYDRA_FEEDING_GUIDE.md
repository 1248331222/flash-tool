# 🐉 Hydra 九头蛇喂养指南

> 版本：v1.0 | 适用 Hydra 引擎：v0.1+

---

## 一、喂养哲学

Hydra（九头蛇）的成长依靠持续喂养。每遇到一个解析失败的刷机脚本，就是 Hydra 成长的机会。

**喂养三步曲：**
1. **收集** — 遇到解析失败的脚本，放入样本目录
2. **分析** — 找出引擎无法处理的具体语法特性
3. **投喂** — 编写测试用例，完善解析逻辑

---

## 二、目录结构

```
flash_tool/
├── hydra_samples/           # 样本脚本库
│   ├── bat/                 # BAT 样本（3个参考样本）
│   ├── sh/                  # SH 样本（2个参考样本）
│   ├── community/           # 社区贡献样本（新脚本放这里）
│   └── edge_cases/          # 边界情况样本（特殊语法）
├── hydra_tests/             # 测试框架
│   ├── __init__.py
│   └── test_hydra.py        # 25 项自动化测试
└── core/hydra/              # 引擎核心
    ├── __init__.py           # HydraEngine 入口
    ├── types.py              # 数据类定义
    ├── ast_parser.py         # AST 解析器
    ├── symbol_table.py       # 变量符号表
    ├── environment.py        # 环境模拟器
    ├── command_extractor.py  # 命令提取器
    ├── complexity_judge.py   # 复杂度判定
    └── execution_tracer.py   # 执行追踪器
```

---

## 三、如何贡献一个脚本

### 步骤 1：放入样本目录

将脚本放入 `hydra_samples/community/` 目录，命名建议：
- 品牌型号描述，如 `xiaomi_umi_flash_all.bat`
- 包含关键语法特征，如 `for_loop_if_else_nested.sh`

### 步骤 2：测试引擎解析效果

```bash
cd /sdcard/123456/flash_tool
python3 -c "
import sys; sys.path.insert(0, '.')
from core.hydra import HydraEngine
e = HydraEngine()
with open('hydra_samples/community/你的脚本.sh') as f:
    content = f.read()
r = e.parse(content, 'sh')  # 或 'bat'
print(f'步骤数: {r.total_steps}')
print(f'是否简单: {r.is_simple}')
print(f'警告: {r.warnings}')
for s in r.steps:
    print(f'  {s.type} {s.part} -> {s.fileName}')
"
```

### 步骤 3：添加测试用例

在 `hydra_tests/test_hydra.py` 的 `_build_tests()` 方法末尾添加：

```python
self.tests.append(HydraTestCase(
    "社区: 你的描述",
    open("hydra_samples/community/你的脚本.sh").read(),
    script_type="sh",
    expected_steps=N,          # 期望解析出的步骤数
    expected_simple=True,      # 是否标记为简单脚本
    category="社区贡献",
    known_complex=False,       # True 表示已知复杂（期望失败）
))
```

### 步骤 4：运行全部测试

```bash
python3 hydra_tests/test_hydra.py
```

---

## 四、引擎能力清单（当前支持）

### 基础 fastboot 命令

| 命令 | 示例 | 状态 |
|------|------|------|
| `flash` | `fastboot flash boot boot.img` | ✅ |
| `erase` | `fastboot erase userdata` | ✅ |
| `reboot` | `fastboot reboot` | ✅ |
| `reboot-bootloader` | `fastboot reboot-bootloader` | ✅ |
| `getvar` | `fastboot getvar product` | ✅ |
| `devices` | `fastboot devices` | ✅ |
| `oem` | `fastboot oem unlock` | ✅ |
| `-w` | `fastboot -w` | ✅ |

### BAT 语法

| 语法 | 示例 | 状态 |
|------|------|------|
| `%VAR%` 变量 | `%FASTBOOT% flash boot boot.img` | ✅ |
| `%~dp0` 路径修饰符 | `%~dp0tools\\fastboot.exe` | ✅ |
| `set VAR=value` | `set IMG_DIR=images` | ✅ |
| `for /L %%i in (...) do` | 数值循环 | ✅ |
| `for %%i in (list) do` | 列表循环 | ✅ |
| `if exist` | 文件存在性检查 | ✅ |
| `if == / equ` | 字符串/数值比较 | ✅ |
| `if defined` | 变量定义检查 | ✅ |
| `if-else` | 双分支条件 | ✅ |
| `goto :label` | 跳转 | ✅ |
| `call :label` | 调用子过程 | ✅ |
| `setlocal enabledelayedexpansion` | 延迟扩展 | ✅ |
| `!VAR!` 延迟变量 | 运行时变量展开 | ✅ |
| `%VAR:old=new%` | 字符串替换 | ✅ |
| `%VAR:~start,len%` | 字符串切片 | ✅ |
| `for /F` | 文件解析循环 | ⚠️ 基础 |

### SH 语法

| 语法 | 示例 | 状态 |
|------|------|------|
| `$VAR` / `${VAR}` | `$FASTBOOT flash boot boot.img` | ✅ |
| `${VAR:-default}` | `${FASTBOOT:-fastboot}` | ✅ |
| `var=value` | `FASTBOOT=fastboot` | ✅ |
| `$(...)` 子 shell | `DEVICE=$(getprop ro.product.device)` | ⚠️ 值保留但不展开 |
| `for ... do ... done` | 列表循环 | ✅ |
| `if ... then ... fi` | 条件 | ✅ |
| `if ... then ... else ... fi` | 双分支 | ✅ |
| `while ... do ... done` | while 循环 | ⚠️ 标记动态 |
| `case ... esac` | 分支匹配 | ✅ |
| `function name() { ... }` | 函数定义 | ✅ |
| `name() { ... }` | 函数定义（简写） | ✅ |
| `函数调用展开` | `flash_partition "boot" "boot.img"` | ✅ |
| `位置参数 $1 $2 ...` | 函数参数传递 | ✅ |
| `local var=value` | 局部变量 | ✅ |
| `export/readonly` | 环境变量 | ✅ |
| `$(echo ... \| sed ...)` | 管道子 shell | ⚠️ 无法展开 |
| `[ -f path ]` 文件检查 | 条件中的文件存在性 | ✅ |
| `[ a = b ]` 字符串比较 | 条件比较 | ✅ |
| `[ a -eq b ]` 数值比较 | 数值比较 | ✅ |

### 嵌套/复合结构

| 结构 | 状态 |
|------|------|
| for 循环嵌套 if | ✅ |
| if 嵌套 if | ✅ |
| for 循环调用函数 | ✅ |
| 函数内调用函数 | ⚠️ 一级 |
| while 嵌套 if | ✅ |
| 三层以上嵌套 | ⚠️ 依赖模拟深度 |

---

## 五、已知无法处理的语法

这些语法特征会导致脚本被标记为 `complex`，需要用真实执行追踪（ExecutionTracer）补充：

1. **动态变量名** (`!VAR!` 在循环中改变)
   - 示例：`set "PART=slot_a"` 然后在循环中改 `PART`
   - 状态：循环变量追踪
   
2. **非标准 fastboot 路径**
   - 示例：通过 `adb` 推送后执行，或通过变量函数间接调用
   
3. **交互式等待**
   - 示例：`pause`、`choice`、`read -p`
   
4. **外部命令依赖**
   - 示例：`adb reboot bootloader`、`python generate_image.py`
   
5. **`while`/`until` 不确定循环**
   - 状态：标记动态，提取体内命令但无法确定次数
   
6. **`for /F` 文件解析循环**
   - 示例：`for /F "tokens=*" %%i in (list.txt) do`
   
7. **管道和重定向中的命令**
   - 示例：`fastboot devices 2>/dev/null | grep "fastboot"`
   
8. **算术运算中的命令**
   - 示例：`set /a count+=1`

---

## 六、喂养优先级

按照收益/难度排序：

| 优先级 | 任务 | 难度 | 收益 |
|--------|------|------|------|
| P0 | 收集更多真实刷机脚本 | ★☆☆ | 高 |
| P1 | 支持 `for /F` 文件解析 | ★★☆ | 中 |
| P2 | 多级函数调用展开 | ★★☆ | 中 |
| P3 | 管道命令中的 fastboot 提取 | ★★★ | 低 |
| P4 | `adb reboot bootloader` 识别 | ★☆☆ | 中 |
| P5 | 子 shell `$(...)` 展开（简单模式） | ★★★ | 低 |
| P6 | Python 执行追踪器远程执行 | ★★★★ | 高 |

---

## 七、测试框架使用

### 运行测试
```bash
cd /sdcard/123456/flash_tool
python3 hydra_tests/test_hydra.py
```

### 添加分类
在 `HydraTestCase` 构造函数中设置 `category` 参数：
```python
HydraTestCase(
    "描述", content,
    script_type="bat",
    expected_steps=3,
    category="你的分类",  # 影响分类统计
)
```

### 标记已知复杂
如果某个脚本包含当前引擎无法处理的语法（如 while 循环），标记为 `known_complex=True`：
```python
HydraTestCase(
    "包含 while 循环的脚本", content,
    expected_steps=0,  # 期望0步
    expected_simple=False,
    known_complex=True,  # 已知复杂，不统计为失败
    category="社区贡献",
)
```

---

## 八、提交清单

贡献一个新脚本时，请确认：

- [ ] 脚本放在 `hydra_samples/community/` 或 `hydra_samples/edge_cases/`
- [ ] 脚本不包含敏感信息（设备序列号、密码等）
- [ ] 已在本地运行 `test_hydra.py` 全部通过
- [ ] 已在 `_build_tests()` 中添加对应的测试用例
- [ ] 测试用例的 `expected_steps` 与 `HydraEngine.parse()` 实际输出一致
- [ ] 如果测试失败，已添加 `known_complex=True` 并说明原因
- [ ] 更新了本指南中的能力清单（如果新增了支持语法）

---

**Happy Feeding! 🐉**
