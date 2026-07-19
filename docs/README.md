# 天树刷机 (Skytree Flasher) — GitHub Pages 单文件部署版

> 版本：**v4.0.6** (2026-07-19)
> 体积：约 1.1 MB（单文件 `index.html`，无需任何依赖文件）

本目录是天树刷机的**单文件前端版**，专为 GitHub Pages 部署设计。
所有 CSS、JavaScript、ES Module、图片资源均已内联进一个 `index.html` 文件中，
无需额外配置构建工具，**直接上传即可使用**。

---

## 📦 目录内容

| 文件 | 说明 |
| --- | --- |
| `index.html` | 单文件前端（核心文件，1.1 MB） |
| `.nojekyll` | 禁止 GitHub Pages 的 Jekyll 处理（必须保留） |
| `README.md` | 本说明文档 |

---

## 🚀 部署到 GitHub Pages（3 分钟完成）

### 步骤 1：创建仓库

1. 登录 GitHub，点击右上角 **+** → **New repository**
2. Repository name 填：`skytree-flasher`（或任意你喜欢的名字）
3. 可见性选 **Public**（GitHub Pages 免费版需要公开仓库）
4. **不要**勾选 "Initialize this repository with a README"
5. 点击 **Create repository**

### 步骤 2：上传文件

#### 方式 A：网页直接上传（推荐新手）

1. 进入刚创建的仓库页面
2. 点击 **uploading an existing file** 链接
3. 把本目录下的 `index.html` 和 `.nojekyll` 两个文件拖入上传区
   （`.nojekyll` 是隐藏文件，如果看不到请直接拖拽，或用命令行上传）
4. Commit message 填：`v4.0.6 单文件部署`
5. 点击 **Commit changes**

#### 方式 B：Git 命令行上传

```bash
# 克隆空仓库
git clone https://github.com/<你的用户名>/skytree-flasher.git
cd skytree-flasher

# 复制本目录下的文件到仓库根目录
cp /path/to/index.html .
cp /path/to/.nojekyll .

# 提交并推送
git add .
git commit -m "v4.0.6 单文件部署"
git push origin main
```

### 步骤 3：开启 GitHub Pages

1. 在仓库页面点击 **Settings** 标签
2. 左侧菜单找到 **Pages**
3. **Source** 选择 **Deploy from a branch**
4. **Branch** 选择 `main`，文件夹选 `/ (root)`
5. 点击 **Save**

### 步骤 4：等待并访问

- 保存后约 1-3 分钟，GitHub 会完成部署
- 访问地址：`https://<你的用户名>.github.io/skytree-flasher/`
- 部署成功后页面顶部会显示绿色 ✅ 提示

---

## ⚙️ 使用说明

### 首次使用配置后端地址

由于 GitHub Pages 只托管前端页面，**后端服务需要你自己部署**（详见后端部署章节）。

1. 打开你的 GitHub Pages 页面
2. 在「设备连接」页面找到 **后端地址** 输入框
3. 填入你的后端服务器地址，例如：`http://192.168.1.100:5000`
4. 点击 **应用** 按钮
5. 地址会自动保存到浏览器 localStorage，下次访问无需重新填写

### 两种运行模式

| 模式 | 说明 | 适用场景 |
| --- | --- | --- |
| **后端模式** | 通过你部署的 Termux 后端执行 fastboot/adb 命令 | 完整刷机功能（推荐） |
| **WebUSB 模式** | 浏览器直接通过 WebUSB 连接设备 | 浏览器直连，无需后端（线刷大文件受限） |

> WebUSB 模式需要使用 **Chrome/Edge 浏览器**，且页面必须通过 HTTPS 访问（GitHub Pages 默认是 HTTPS，✅ 满足要求）。

---

## 🖥️ 后端服务部署（后端模式必需）

单文件前端只负责界面，刷机命令需要后端执行。后端运行在 **Termux**（Android）上。

### 后端环境要求

- Android 手机 + Termux APP
- Termux 已安装：`python`、`android-tools`（提供 adb/fastboot）、`termux-api`
- OTG 线 + 被刷手机

### 后端部署步骤

1. 把完整项目（`flash_tool_project_new/` 目录）复制到 Termux 中
2. 安装 Python 依赖：
   ```bash
   pip install flask flask-socketio python-dotenv pyusb
   ```
3. 启动后端：
   ```bash
   cd flash_tool_project_new
   python app.py
   ```
4. 后端默认监听 `0.0.0.0:5000`
5. 在 Termux 中执行 `ifconfig` 查看手机 IP，例如 `192.168.1.100`
6. 在 GitHub Pages 前端页面的「后端地址」填入 `http://192.168.1.100:5000`

### 后端 CORS 配置

后端需要允许你的 GitHub Pages 域名跨域访问。在 `config.py` 中配置：

```python
ALLOWED_ORIGINS = [
    "https://<你的用户名>.github.io",
    "http://127.0.0.1:5000",  # 本地调试
]
```

---

## 🔧 技术实现说明

### 单文件如何容纳 ES Module

项目中 `webusb.js` 是 ES Module，它通过 `import` 引入 `fastboot.mjs` 和 `adb.bundle.mjs`。
单文件版采用 **import map + data URL** 技术解决：

1. 把 `fastboot.mjs` 和 `adb.bundle.mjs` 转成 base64 data URL
2. 用 `<script type="importmap">` 把这两个 URL 映射为 `fastboot-lib` 和 `adb-lib`
3. `webusb.js` 中的 `import ... from '../lib/fastboot.mjs'` 改写为 `from 'fastboot-lib'`
4. 把改写后的 `webusb.js` 内联进 `<script type="module">`

这样浏览器在解析 ES Module 时会通过 import map 找到 data URL 中的库代码，无需额外文件请求。

### 资源内联清单

| 资源类型 | 数量 | 内联方式 |
| --- | --- | --- |
| CSS 文件 | 6 个 | 合并进单个 `<style>` 标签 |
| 普通 JS 文件 | 22 个 | 合并进单个 `<script>` 标签 |
| ES Module (webusb.js) | 1 个 | 内联进 `<script type="module">` |
| .mjs 库文件 | 2 个 | base64 data URL + import map |
| 图片资源 | 1 个 PNG | base64 data URI |
| 外部依赖 | socket.io | 保留 CDN 引用 |

### 外部 CDN 依赖

单文件版唯一的外部依赖是 **socket.io**（用于实时日志推送）：

```html
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
```

如果部署环境无法访问 CDN，可手动下载 socket.io.min.js 并内联进 HTML，或部署到自己的 CDN。

---

## 🛠️ 重新构建单文件

如果修改了源码，需要重新生成单文件：

```bash
# 构建脚本位于源码项目的临时目录
python build_single_file.py

# 输出：/data/user/work/single_file/index.html
```

构建脚本会：
1. 读取 `flash_tool_project_new/static/` 下所有资源
2. 内联 CSS、JS、图片
3. 用 import map + data URL 处理 ES Module
4. 输出单个 `index.html`

---

## ❓ 常见问题

### Q1: 打开页面是空白？

**A:** 检查浏览器控制台（F12）是否有错误。常见原因：
- `.nojekyll` 文件未上传，导致 GitHub Pages 用 Jekyll 处理了文件
- 仓库是 Private，GitHub Pages 免费版不支持私有仓库

### Q2: 后端地址填了但连不上？

**A:** 检查：
1. 后端 Termux 是否已启动 `python app.py`
2. 手机和被刷设备是否在同一网络
3. 后端 `config.py` 的 `ALLOWED_ORIGINS` 是否包含你的 GitHub Pages 域名
4. 防火墙是否放行 5000 端口

### Q3: WebUSB 模式无法识别设备？

**A:** WebUSB 要求：
1. 使用 Chrome/Edge 浏览器
2. 页面通过 HTTPS 访问（GitHub Pages ✅ 满足）
3. 手机需要支持 OTG 并已授权
4. 被刷设备需处于 ADB 模式或 Fastboot/Bootloader 模式

### Q4: 单文件版和完整版功能有区别吗？

**A:** **功能完全一致**。单文件版只是把多个文件合并成一个，所有刷机、WebUSB、自定义命令、工作台等功能都保留。唯一区别是 socket.io 走 CDN。

### Q5: 可以部署到其他静态托管吗？

**A:** 可以。单文件版兼容任何静态托管服务：
- Vercel
- Netlify
- Cloudflare Pages
- 腾讯云 COS / 阿里云 OSS（静态网站托管）
- 任意 Nginx 服务器

只要把 `index.html` 上传到网站根目录即可。

---

## 📝 版本信息

- **当前版本**：v4.0.6
- **发布日期**：2026-07-19
- **作者联系方式**：微信 `KS30618`

### v4.0.6 更新内容

- 新增：自定义命令支持会话工作目录持久化（cd 命令真正生效）
  - 纯 cd 命令会更新会话工作目录，后续命令在新目录下执行
  - 支持 cd /path、cd ~、cd ../path、cd relative/path 等形式
  - 界面显示当前工作目录（📁 标识），cd 成功后显示新目录
  - 新增 /api/shell/cwd 和 /api/shell/reset 接口
  - 会话 2 小时未活跃自动清理，最多保留 50 个会话

完整更新日志见页面内「版本」页面的「更新日志」区域。

---

## 📄 License

本前端代码供天树刷机用户自由部署自用。如需二次分发或商用，请联系作者。
