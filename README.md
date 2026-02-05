# Card Snapshot 📸

智能从网页中导出卡片元素为 PNG 图片的命令行工具。

## ✨ 特性

- **自动检测选择器** - 自动识别 `.card`、`.poster-card` 等常见卡片元素
- **自动检测 iframe** - 自动发现并处理嵌套在 iframe 中的内容
- **自动生成输出目录** - 根据 URL 或文件名智能命名输出目录
- **懒加载支持** - 两轮滚动策略确保动态加载的内容正确渲染
- **精确优先** - 精确选择器优先于模糊匹配，避免误选

## 🚀 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/yourusername/card-snapshot.git
cd card-snapshot

# 安装依赖
pip install -r requirements.txt

# 安装浏览器（首次运行需要）
python -m playwright install chromium
```

### 使用

```bash
# 最简单的用法 - 全自动检测
python card_snapshot.py "https://example.com"

# 指定选择器
python card_snapshot.py "https://example.com" -s ".card"

# 本地 HTML 文件
python card_snapshot.py "page.html"
```

## 📖 使用示例

### 自动检测（推荐）

```bash
# 工具会自动检测选择器和 iframe
python card_snapshot.py "https://youmind.com/a/xxx"

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
python card_snapshot.py "https://example.com" --list-selectors

# 显示浏览器窗口
python card_snapshot.py "https://example.com" --show-browser
```

### 自定义输出

```bash
# 自定义输出目录
python card_snapshot.py "https://example.com" -o "./my-cards"

# 自定义文件名前缀
python card_snapshot.py "https://example.com" --prefix "poster"
# 输出: poster-01.png, poster-02.png, ...
```

### 手动指定 iframe

```bash
# 如果自动检测不准确，可以手动指定
python card_snapshot.py "https://example.com" -f "cdn.example.com"
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

## 🔍 自动检测逻辑

### 选择器检测

工具会按以下优先级检测卡片选择器：

**精确选择器**（优先）：
- `.poster-card`
- `.card`
- `.post-card`
- `.article-card`
- `.item-card`
- `.grid-item`
- `.slide`

**模糊选择器**（后备）：
- `[class*='card']`
- `[class*='item']`

### iframe 检测

如果页面包含 iframe，工具会自动扫描每个 iframe，检测是否包含卡片元素。

### 输出目录生成

- URL: `https://example.com/page/cards` → `outputs/cards-example-cards`
- 本地文件: `my-page.html` → `outputs/cards-my-page`

## 📝 实际案例

### YouMind 卡片导出

```bash
python card_snapshot.py "https://youmind.com/a/fUEcFwITYVgR5q"
# 自动检测到 iframe 和 .poster-card 选择器
# 导出 11 张卡片到 outputs/cards-youmind-fUEcFwITYVgR5q/
```

### Lovart 卡片导出

```bash
python card_snapshot.py "https://assets-persist.lovart.ai/agent_images/xxx.html"
# 自动检测到 .card 选择器
# 导出 7 张卡片到 outputs/cards-assets-persist-agent_images/
```

### BibiGPT 卡片导出

```bash
python card_snapshot.py "https://bibigpt.co/share/html/xxx"
# 自动检测到 iframe 和 .card 选择器
# 导出 9 张卡片到 outputs/cards-bibigpt-html/
```

## 🛠️ 故障排除

### 未检测到卡片元素

```bash
# 使用 --list-selectors 查看页面中的选择器
python card_snapshot.py "https://example.com" --list-selectors

# 然后手动指定
python card_snapshot.py "https://example.com" -s ".your-selector"
```

### 内容未完全加载

```bash
# 显示浏览器窗口检查
python card_snapshot.py "https://example.com" --show-browser
```

### 超时错误

页面加载超时默认为 60 秒。如果页面加载很慢，可能需要修改源码中的 timeout 值。

## 📄 License

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
