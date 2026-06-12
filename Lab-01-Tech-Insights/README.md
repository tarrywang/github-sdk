# Lab-01：EV 市场洞察与竞争雷达 — GitHub Agentic Workflows 动手实验

本实验带你从零跑通一个基于 GitHub Agentic Workflows 的 EV（电动车）行业市场洞察与竞争雷达流水线。

实验时长：60 分钟

你将收获：Fork 仓库 → 配置 gh-aw → 手动触发工作流 → 查看 AI 生成的 EV 市场洞察报告 → 部署到 GitHub Pages。

### 架构图

```text
RSS 源 (10 个 EV 精选)
    ↓ 阶段1: 信号抓取
MCP Scripts (Python 工具)
    ↓ raw_signals.json
    ↓ 阶段2: 热点聚类
LLM (Copilot) + cluster_or_fallback
    ↓ hotspots.json
    ↓ 阶段3: 洞察生成
LLM (Copilot) + insight_or_fallback
    ↓ insights.json
    ↓ 阶段4: 报告生成
LLM (Copilot) + render_report_or_fallback
    ↓ report.md
    ↓ safe-outputs 自动创建 PR
合并 PR → deploy-pages 自动触发
    ↓
GitHub Pages (在线查看)
```

---

## Lab 0: 环境准备与 Fork（10 分钟）

### 前置条件
- GitHub 账号（需要 GitHub Copilot 订阅）
- 一台能上网的电脑（macOS / Linux / Windows WSL）
- Python 3.10+ 已安装
- VS Code 已安装（推荐）

### 步骤

1. Fork 本仓库
   - 打开 `https://github.com/ITD-NextDimension/github-sdk`
   - 点击右上角 **Fork** 按钮
   - 保留默认设置，点击 **Create fork**
   - 等待 Fork 完成

2. Clone 到本地
```bash
git clone https://github.com/<你的用户名>/github-sdk.git
cd github-sdk
```

3. 安装 GitHub CLI
```bash
# macOS
brew install gh

# Linux (Debian/Ubuntu)
sudo apt install gh

# Windows
winget install GitHub.cli
```

4. 登录 GitHub CLI
```bash
gh auth login
# 选择 GitHub.com → HTTPS → 按提示完成浏览器认证
```

5. 安装 gh-aw 扩展
```bash
gh extension install github/gh-aw
```

6. 验证安装
```bash
gh aw --version
python3 --version  # 确认 3.10+
```

---

## Lab 1: 理解项目结构（10 分钟）

用 VS Code 打开项目，浏览以下文件：

1. 打开工作流文件：`.github/workflows/tech-insight.md`
   - YAML frontmatter 结构说明：
     - `name:` 工作流名称
     - `on: workflow_dispatch:` 手动触发
     - `permissions: contents: read` 允许读取仓库内容（写入通过 safe-outputs 机制）
     - `tools:` 声明 `bash` 和 `edit` 两个内置工具
     - `mcp-scripts:` 定义 7 个 MCP Script Python 工具（抓取、聚类、洞察、报告等）
     - `engine: copilot` 使用 GitHub Copilot 作为 AI 引擎
     - `network: allowed:` 显式域名白名单（列出所有允许访问的 RSS 源域名）
   - Markdown 正文是给 AI 的自然语言指令，分为 4 个阶段。

2. 浏览 MCP Scripts 目录：`Lab-01-Tech-Insights/mcp-scripts/`
   - 核心工具功能如下：

| 脚本 | 功能 |
|------|------|
| tech_read_source_list.py | 读取 RSS 源列表配置 |
| tech_fetch_all_to_disk.py | 并行抓取所有源的内容 |
| tech_load_articles_from_disk.py | 加载并过滤有效文章 |
| tech_cluster_or_fallback.py | 对文章进行热点聚类 |
| tech_insight_or_fallback.py | 生成每个热点的洞察分析 |
| tech_render_report_or_fallback.py | 渲染 Markdown 报告 |
| write_text_file.py | 文件写入工具 |

3. 查看数据源：`Lab-01-Tech-Insights/input/api/rss_list.json`
   - 包含 10 个精选 EV 行业 RSS 源（以中国新能源车市为主，兼顾全球 EV 媒体）。
   - 每个源有 `signal_level`（S/A/B）字段，权重分别为 30/20/10，影响热点排序。

4. 查看前端：`Lab-01-Tech-Insights/frontend/`
   - `index.html` + `main.js` 实现浏览器端 Markdown 渲染为 HTML。

> 💡 **核心概念**：gh-aw 将「Markdown + YAML frontmatter」编译成标准 GitHub Actions 工作流。AI agent 在 Actions runner 中执行，调用你定义的工具（MCP Scripts），完成复杂任务。

---

## Lab 2: 配置认证与首次运行（20 分钟）

这是最重要的一步，成功运行你的第一个 Agentic Workflow！

### 步骤 1: 在 GitHub 上启用 Actions
- 打开你 Fork 的仓库页面。
- 点击 **Settings** → 左侧 **Actions** → **General**。
- 确认 Actions permissions 已开启（Allow all actions）。

### 步骤 2: 设置 Copilot Token（关键步骤）
- 前往 https://github.com/settings/tokens?type=beta 创建 **Fine-grained Personal Access Token**
  （必须是 fine-grained PAT，gh-aw 不支持 GitHub App / OAuth token）。
  - Token name: `copilot-token`
  - Expiration: 30 days
  - Repository access: All repositories
  - **Permissions → Account permissions**：将 **Copilot Requests** 设为 **Read** access。
    > ⚠️ 这是关键权限，且位于 **Account permissions** 下 —— 不要错加成 Repository permissions 里的
    > 「Copilot agent settings」。权限加错位置会导致 `Authentication failed ... (HTTP 401)`。
- 回到你的 Fork 仓库 → **Settings** → **Secrets and variables** → **Actions**。
- 点击 **New repository secret**。
  - Name: `COPILOT_GITHUB_TOKEN`
  - Value: 粘贴刚才的 Token。
  - 点击 **Add secret**。

> ⚠️ **注意**：需要你的 GitHub 账号有 Copilot 订阅才能使用 Copilot 引擎。

### 步骤 3: 编译 gh-aw 工作流
```bash
cd github-sdk
gh aw compile .github/workflows/tech-insight.md
```
- 这会在同目录生成 `tech-insight.lock.yml`，即编译后的 GitHub Actions YAML 文件。

### 步骤 4: 推送编译结果
```bash
git add .github/workflows/
git commit -m "chore: compile gh-aw workflow"
git push origin main
```

### 步骤 5: 手动触发工作流
- **方法 A（推荐）**：在 GitHub UI 页面。
  - 打开仓库 → **Actions** 标签页。
  - 左侧选择 **EV Insight Workflow**。
  - 点击 **Run workflow** → **Run workflow**。
- **方法 B（CLI）**：
```bash
gh workflow run "EV Insight Workflow"
```

### 步骤 6: 观察运行
- 在 Actions 页面点击正在运行的 workflow run。
- 展开 `agent` job 查看实时日志（这是 AI 执行主要工作的步骤）。
- 工作流一般需要 **15-20 分钟**完成（其中 agent 步骤约 10-15 分钟）。

### 步骤 7: 合并 PR 并检查输出
- 运行成功后，工作流会通过 safe-outputs 机制**自动创建一个 PR**（标题以 `[ev-insight]` 开头）。
- 在仓库 **Pull requests** 标签页找到该 PR，Review 后点击 **Merge**。
- 合并后拉取最新代码：
```bash
git pull origin main
```
- 查看生成的文件：
  - `Lab-01-Tech-Insights/output/raw_signals.json`
  - `Lab-01-Tech-Insights/output/clusters/hotspots.json`
  - `Lab-01-Tech-Insights/output/insights/insights.json`
  - `Lab-01-Tech-Insights/output/report.md`

---

## Lab 3: 查看报告与本地预览（10 分钟）

1. 在 VS Code 中打开报告：
```bash
code Lab-01-Tech-Insights/output/report.md
```
- 观察报告结构：市场摘要 → 跨源趋势 → 重要单条更新 → 车企竞争雷达 → 新车型与产品发布 → 政策与销量 → 技术与电池研究。

2. 本地预览前端：
```bash
python3 -m http.server 8000 --directory Lab-01-Tech-Insights/frontend
```
- 在浏览器打开 `http://localhost:8000`。
- 查看 Markdown 渲染成 HTML 的效果。

3. 理解渲染流程：
- `main.js` 使用 `fetch()` 加载 `report.md`。
- 用 `marked.js` 将 Markdown 转换为 HTML。

> 💡 **思考题**：如果你想更改报告的显示样式，应该修改哪个文件？（答案：`styles.css`）

---

## Lab 4: 实验 — 定时触发与 GitHub Pages（10 分钟）

### 实验 A: 添加定时触发

1. 编辑 `.github/workflows/tech-insight.md` 的 frontmatter 部分。
2. 将 `on:` 修改为：
```yaml
on:
  workflow_dispatch:
  schedule: daily around 9am utc+8
```

3. 重新编译并推送。

### 实验 B: 开启 GitHub Pages

1. 打开仓库 → **Settings** → 左侧 **Pages**。
2. Source 选择 **GitHub Actions**。
3. GitHub Pages 会在以下情况自动部署：
   - 当 `Lab-01-Tech-Insights/frontend/` 目录有文件变更被推送到 `main` 分支时（例如合并 EV Insight PR 后）。
   - 也可以手动触发：
```bash
gh workflow run "Deploy GitHub Pages"
```
4. 访问 `https://<你的用户名>.github.io/github-sdk/` 查看在线版报告。

> 💡 完整发布链路：EV Insight 工作流完成 → safe-outputs 创建 PR → 合并 PR → `frontend/report.md` 变更触发 deploy-pages → GitHub Pages 自动更新。

---

## 总结与下一步

你在本实验中学到了：
- ✅ gh-aw 的核心概念：Markdown 工作流 + MCP Scripts + AI Engine。
- ✅ 如何安装、编译和运行 Agentic Workflows。
- ✅ 如何设置定时触发和 GitHub Pages 部署。

延伸探索：
- 尝试切换 AI 引擎：`engine: claude`。
- 添加 safe-outputs 自动创建 Issue。
- 探索更多 gh-aw 设计模式：https://github.github.com/gh-aw/

---

## 附录 A: 目录结构参考
```text
github-sdk/
├── .github/workflows/
│   ├── tech-insight.md           # gh-aw 工作流定义
│   ├── tech-insight.lock.yml     # 编译后的 Actions YAML
│   └── deploy-pages.yml          # Pages 部署工作流
├── Lab-01-Tech-Insights/
│   ├── mcp-scripts/              # MCP Script 工具
│   ├── input/api/rss_list.json   # 数据源（10 个 EV 精选 RSS）
│   ├── frontend/                 # 展示前端
│   └── output/                   # 运行时输出
```

## 附录 B: 常见问题

1. **`gh aw compile` 报错**：检查 YAML frontmatter 格式，确保三横线 `---` 完整。
2. **工作流运行失败**：检查 `COPILOT_GITHUB_TOKEN` 是否正确设置在 Secret 中。
3. **网络抓取超时**：可以在工作流配置中增加 `timeout_seconds`。
4. **GitHub Pages 404**：确认 Settings → Pages 中的 Source 设置为 GitHub Actions。
5. **查看思考过程**：在 Actions 日志中展开对应的 agent 步骤即可查看。

## 附录 C: 参考链接
- gh-aw 官方文档: https://github.github.com/gh-aw/
- GitHub CLI 安装: https://cli.github.com
