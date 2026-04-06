# Card Snapshot 📸

智能从网页中导出卡片元素为 PNG 图片的命令行工具。

## ✨ 特性

- **自动检测选择器** — 自动识别 `.card`、`.poster-card` 等常见卡片元素
- **自动检测 iframe** — 自动发现并处理嵌套在 iframe 中的内容
- **自动生成输出目录** — 根据 URL 或文件名智能命名输出目录
- **懒加载支持** — 两轮滚动策略确保动态加载的内容正确渲染
- **精确优先** — 精确选择器优先于模糊匹配，避免误选
- **崩溃自动恢复** — 遇到大页面渲染崩溃时，自动切换到隔离模式逐张截图

## 🚀 快速开始

### 安装

**方式一：pip 直接安装（推荐）**

```bash
pip install git+https://github.com/violin86318/card-snapshot.git

# 安装浏览器引擎（首次运行需要）
python -m playwright install chromium
```

**方式二：克隆源码安装**

```bash
git clone https://github.com/violin86318/card-snapshot.git
cd card-snapshot
pip install -e .

# 安装浏览器引擎（首次运行需要）
python -m playwright install chromium
```

安装后即可在终端使用 `card-snapshot` 命令。

### 使用

```bash
# 最简单的用法 - 全自动检测
card-snapshot "https://example.com"

# 指定选择器
card-snapshot "https://example.com" -s ".card"

# 本地 HTML 文件
card-snapshot "page.html"
```

## 📖 使用示例

### 自动检测（推荐）

```bash
# 工具会自动检测选择器和 iframe
card-snapshot "https://youmind.com/a/xxx"

# 输出:
# 🎯 目标: https://youmind.com/a/xxx
# 📄 正在加载页面...
# 🔍 自动检测到 iframe: https://cdn.gooo.ai/artifacts/...
# 🔍 自动检测选择器...
#    找到选择器: .poster-card (11 个元素)
# 📦 找到 11 个卡片
# 📁 输出目录: outputs/cards-youmind-xxx
```

### 调试模式

```bash
# 列出检测到的选择器（不导出）
card-snapshot "https://example.com" --list-selectors

# 显示浏览器窗口
card-snapshot "https://example.com" --show-browser
```

### 自定义输出

```bash
# 自定义输出目录
card-snapshot "https://example.com" -o "./my-cards"

# 自定义文件名前缀
card-snapshot "https://example.com" --prefix "poster"
# 输出: poster-01.png, poster-02.png, ...
```

### 手动指定 iframe

```bash
# 如果自动检测不准确，可以手动指定
card-snapshot "https://example.com" -f "cdn.example.com"
```

## ⚙️ 参数说明

| 参数 | 缩写 | 默认值 | 说明 |
|------|------|--------|------|
| `target` | - | (必填) | 网页 URL 或本地 HTML 文件路径 |
| `--selector` | `-s` | (自动检测) | 卡片元素的 CSS 选择器 |
| `--frame` | `-f` | (自动检测) | iframe URL 包含的字符串 |
| `--output` | `-o` | (自动生成) | 输出目录 |
| `--prefix` | - | `card` | 输出文件名前缀 |
| `--width` | `-w` | `1600` | 浏览器视口宽度 |
| `--height` | `-H` | `1200` | 浏览器视口高度 |
| `--show-browser` | - | - | 显示浏览器窗口（调试用） |
| `--list-selectors` | - | - | 只列出检测到的选择器 |
| `--browser` | - | `chromium` | 浏览器引擎: chromium/firefox/webkit |

## 🔍 自动检测逻辑

### 选择器检测

工具会按以下优先级检测卡片选择器：

**精确选择器**（优先）：
- `.page` / `.poster-card` / `.card`
- `.post-card` / `.article-card` / `.item-card`
- `.grid-item` / `.slide`

**模糊选择器**（后备）：
- `[class*='card']`
- `[class*='item']`

### iframe 检测

如果页面包含 iframe，工具会自动扫描每个 iframe，检测是否包含卡片元素。

### 输出目录生成

- URL: `https://example.com/page/cards` → `outputs/cards-example-cards`
- 本地文件: `my-page.html` → `outputs/cards-my-page`

## 🛠️ 故障排除

### 浏览器崩溃 (Target crashed)

工具内置了**自动崩溃恢复**机制：

1. 首先尝试正常截图
2. 如果检测到渲染进程崩溃，自动切换到**隔离模式**
3. 隔离模式：为每张卡片创建独立的浏览器 context，隐藏其他卡片，逐张截图

如果隔离模式仍然失败，可以尝试使用 WebKit：

```bash
python -m playwright install webkit
card-snapshot "your-page.html" --browser webkit
```

### 未检测到卡片元素

```bash
# 使用 --list-selectors 查看页面中的选择器
card-snapshot "https://example.com" --list-selectors

# 然后手动指定
card-snapshot "https://example.com" -s ".your-selector"
```

### 内容未完全加载

```bash
# 显示浏览器窗口检查
card-snapshot "https://example.com" --show-browser
```

## 📋 在其他电脑安装

```bash
# 一行命令安装
pip install git+https://github.com/violin86318/card-snapshot.git && python -m playwright install chromium
```

## 📄 License

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### Mac 终极防崩溃方案
对于 macOS 用户，当你遇到即便使用了隔离模式依然因为页面过于复杂（如大量深层 SVG 滤镜、复杂的 CSS 混合模式等）而导致 Chromium (Google 引擎) OOM 崩溃的情况，强烈建议使用 **WebKit (Safari 引擎)**：
```bash
card-snapshot "page.html" --browser webkit
```
> WebKit 引擎在 macOS 上能高度穿透系统底层的 CoreGraphics 与 Metal API 甚至虚拟内存调度，对于极高强度的混合滤镜渲染宽容度远超 Chromium，是精美卡片的免死金牌。
