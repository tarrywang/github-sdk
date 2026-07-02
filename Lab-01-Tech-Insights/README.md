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

#### 🐍 本地 Python 版本过低怎么办？（不升级全局 Python 也能跑）

本项目需 Python **3.10+**。若上面 `python3 --version` 低于 3.10，而你又因其他项目依赖、不方便全局升级——**不要动全局 Python**，改用「另装一个新版 + 单独建虚拟环境」，两者互不影响：

1. 另装一个新版 Python（与旧版共存，不覆盖）：
   - macOS（Homebrew）：`brew install python@3.11`
   - Windows：从 <https://www.python.org/downloads/> 下载 3.11 安装包，安装时勾选「Add python.exe to PATH」
   - 跨平台多版本管理：`pyenv install 3.11.9`
2. **用新版**创建虚拟环境（关键：显式写 `python3.11`，而不是默认的 `python3`——`venv` 会继承创建它的那个解释器的版本）：

   ```bash
   # macOS / Linux
   python3.11 -m venv .venv && source .venv/bin/activate
   # Windows（PowerShell）
   py -3.11 -m venv .venv; .venv\Scripts\Activate.ps1
   ```

3. 激活后 `python --version` 应显示 3.11.x，此后 `pip` / `python` 都指向该环境；退出用 `deactivate`（`.venv/` 已在 `.gitignore`，不会提交）。

> 💡 **试一试 · GitHub Copilot CLI（终端里的 AI 助手）**

**练的能力**：新版独立 **Copilot CLI** —— 一个交互式终端 agent，能答疑、给命令、改文件、跑命令；可交互运行 `copilot`，也可 `copilot -p "..."` 非交互。

**怎么做**：

1. 安装（需 Node.js，只需一次）：`npm install -g @github/copilot`（或首次运行 `gh copilot`，gh 会自动下载并透传到它）。
2. 在终端非交互地让它给/解释命令：

```bash
copilot -p "给我在 macOS 用 Homebrew 安装 GitHub CLI 的命令"
copilot -p "解释 git push -f 的作用和风险"
```

**预期结果**：前者通常给出 `brew install gh`，后者逐段解释 `git push -f` 为何危险。想多轮对话、或让它直接帮你执行/改文件，就直接运行 `copilot` 进交互会话（默认每步操作都先征求你同意）。

> 顺手练：装包或 `gh auth login` 报错时，把报错贴进 VS Code Copilot Chat 问「`@terminal` 这个报错怎么解决？」。

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

> 💡 **试一试 · @workspace（让 Copilot 读懂整个 Lab）**

**练的能力**：`@workspace` 参与者 —— Copilot 检索整个项目来回答，最适合快速看懂陌生代码的结构与数据流。

**怎么做**：

1. 在 VS Code 打开本目录，打开 Copilot Chat（Windows/Linux `Ctrl+Alt+I`，macOS `Ctrl+Cmd+I`）。
2. 把下面这句粘贴进去、回车：

```text
@workspace 这个 Lab 的数据从 RSS 一路流到 report.md 经过哪些阶段？每个阶段分别由 mcp-scripts 里的哪个脚本/函数负责？
```

**预期结果**：Copilot 会列出抓取→聚类→洞察→渲染 4 个阶段，并点名 `tech_fetch_all_to_disk` / `tech_cluster_or_fallback` 等函数。

**补充：在 Chat 里引入特定文件的两种方式**

- **方式 1：拖拽文件** —— 直接把文件从 VS Code 资源管理器拖入 Chat 输入框，文件内容会作为上下文附加到本次提问。
- **方式 2：`#file` 快捷方式** —— 在输入框输入 `#file:`，弹出补全后搜索文件名，例如：
  ```text
  #file:Lab-01-Tech-Insights/input/api/rss_list.json 这个文件里有哪些 RSS 源？
  ```

> 顺手练 `/explain`：选中 `mcp-scripts/tech_insight_tools.py` 里 `tech_cluster_or_fallback` 的兜底聚类那段，按 Inline Chat（Win `Ctrl+I` / mac `Cmd+I`）输入 `/explain`，让它逐行讲解阈值与打分。

3. 查看数据源：`Lab-01-Tech-Insights/input/api/rss_list.json`
   - 包含 10 个精选 EV 行业 RSS 源（以中国新能源车市为主，兼顾全球 EV 媒体）。
   - 每个源有 `signal_level`（S/A/B）字段，权重分别为 30/20/10，影响热点排序。

4. 查看前端：`Lab-01-Tech-Insights/frontend/`
   - `index.html` + `main.js` 实现浏览器端 Markdown 渲染为 HTML。

> 💡 **核心概念**：gh-aw 将「Markdown + YAML frontmatter」编译成标准 GitHub Actions 工作流。AI agent 在 Actions runner 中执行，调用你定义的工具（MCP Scripts），完成复杂任务。

> 💡 **试一试 · /tests（让 Copilot 自动补测试）**

**练的能力**：斜杠命令 `/tests` —— 为选中的函数生成单元测试。

**怎么做**：

1. 打开 `mcp-scripts/tech_insight_tools.py`，选中 `_derive_tracks` 整个函数。
2. 按 Inline Chat（Windows/Linux `Ctrl+I`，macOS `Cmd+I`），把下面这句粘贴进去、回车：

```text
/tests 为这个函数生成 pytest 用例，覆盖 beauty / 3c / jewelry 三种品类与 market:* 市场标签的派生，并包含「无匹配」时的兜底分支。
```

**预期结果**：Copilot 生成一组 `pytest` 用例（不同 source 配置 → 期望的 tracks）。务必人工核对断言是否正确，别盲信。

> 顺手练 Ghost Text：在文件里先敲一行函数签名 `def parse_feed(xml: str) -> list[dict]:` 停顿一下，让灰色建议自动补出实现，`Tab` 接受、`Esc` 忽略。完整 Copilot 用法（含 Windows/macOS 快捷键、功能覆盖地图）见仓库根目录《GitHub SDK Workshop 用户操作手册》。

---

## 可选：本地快速验证（不依赖 GitHub Actions / Copilot）

不想先配置 Token、也不想等 Actions 跑完，就想在本地确认整条 Python 工具链能跑通、并立刻看到 `output/`？用仓库自带的本地诊断驱动 `run_local_pipeline.py` 即可。

- **用途**：在零配置（无需 `COPILOT_GITHUB_TOKEN`、无需 Actions）的情况下，本地验证阶段 1–4 的工具链并产出完整 `output/`。
- **原理**：`run_local_pipeline.py` 复用工作流同款的阶段 1–4 工具；阶段 2/3/4 给 LLM 草稿传**空串**，从而触发各工具内置的 `*_or_fallback` 确定性兜底逻辑——因此无需任何 LLM 即可跑通。

**命令（从仓库根目录运行）：**
```bash
# 推荐用虚拟环境（macOS 上 Homebrew Python 默认是 externally-managed，
# 直接 pip install 会报 PEP 668 错误，用 venv 最稳妥；.venv/ 已在 .gitignore 中）
# 若默认 python3 版本 < 3.10，改用新版解释器创建，如 python3.11 -m venv .venv（见「前置条件」的 🐍 说明）
python3 -m venv .venv
.venv/bin/pip install -r Lab-01-Tech-Insights/requirements.txt
.venv/bin/python Lab-01-Tech-Insights/run_local_pipeline.py
```

> 💡 **试一试 · #file / #selection（给 Copilot 精确上下文）**

**练的能力**：上下文变量 `#file`（指定某个文件）、`#selection`（当前选中代码）—— 把对的内容喂给 Copilot，答案才准。

**怎么做**：

1. 本地脚本报错时（如装了依赖但抓取的文章解析为空），打开 Copilot Chat。
2. 把下面这句粘贴进去、回车（`#file:` 会把该文件内容带进上下文）：

```text
#file:.github/workflows/tech-insight.md 这个工作流文件定义了哪些阶段？每个阶段分别做什么？工具调用顺序是怎样的？
```

**预期结果**：Copilot 会结合 `requirements.txt` 的实际内容定位（如 `feedparser` 缺失/版本、编码问题），而不是泛泛而谈。

> 顺手练 `#selection`：选中报错的那几行代码，问「`#selection` 这段为什么会抛异常？」。

> 若你的环境允许全局安装，也可省略 venv，直接 `pip install -r Lab-01-Tech-Insights/requirements.txt && python Lab-01-Tech-Insights/run_local_pipeline.py`。**关键是必须先装好 `feedparser` 等依赖**——否则脚本能跑通但抓取的文章无法解析，最终只会得到一份空的兜底报告。

**产物（落盘到本地）：**
- `Lab-01-Tech-Insights/output/raw_signals.json`
- `Lab-01-Tech-Insights/output/clusters/hotspots.json`
- `Lab-01-Tech-Insights/output/insights/insights.json`
- `Lab-01-Tech-Insights/output/report.md`
- `Lab-01-Tech-Insights/frontend/report.md`

> ⚠️ **与 Actions 版的区别**：本地走的是 fallback 路径，**没有 LLM 参与**，报告是确定性/启发式版本，**质量不等于** Lab 2 中 Copilot 真实生成的报告。本地运行用于快速验证工具链与查看数据流；要拿到真实 AI 洞察报告，仍需走下面 Lab 2 的 Actions 路径。

> 💡 **顺带解答一个常见困惑**：`output/` 在 [.gitignore](../.gitignore) 中被忽略（属运行时产物），所以直接 `git pull` **不会**拉到它。它只会在两种情况下出现在本地——① 你在本地跑上面的脚本；② Actions 工作流跑完后通过 safe-outputs 创建 PR、你合并该 PR 后再 `git pull`。

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

> 💡 **试一试 · Ask 模式（把 Copilot 当文档助手）**

**练的能力**：Ask 模式 —— 只问不改代码，适合查规范、查用法、扫清概念。

**怎么做**：

1. 打开 Copilot Chat（默认就是 Ask 模式）。
2. 把下面这句粘贴进去、回车：

```text
我要在 GitHub Actions 里用 gh-aw 调 GitHub Copilot。fine-grained PAT 需要配哪些权限？Copilot Requests 是在 Account permissions 还是 Repository permissions 下，要设成什么级别？
```

**预期结果**：Copilot 会答 **Account permissions → Copilot Requests = Read**，帮你避开最常见的 `Authentication failed (HTTP 401)`。

### 步骤 3: 编译 gh-aw 工作流
```bash
cd github-sdk
gh aw compile .github/workflows/tech-insight.md
```
- 这会在同目录生成 `tech-insight.lock.yml`，即编译后的 GitHub Actions YAML 文件。

> 💡 **试一试 · /fix（让 Copilot 修报错）**

**练的能力**：斜杠命令 `/fix` —— 针对报错或问题代码给出修复建议。

**怎么做**：

1. `gh aw compile` 报错后，复制终端里那整段报错。
2. 打开 Copilot Chat，把下面这句粘贴进去，再把报错贴在它下面、回车：

```text
/fix 我执行 gh aw compile 时报了下面的错，帮我定位原因并给出修订（多半是 frontmatter 的缩进或缺字段）：
（把上一步复制的报错粘到这一行下面）
```

**预期结果**：Copilot 会指出 YAML frontmatter 的具体问题（缩进、`---` 不成对、字段缺失）并给修订。

> 顺手练：在终端 `copilot -p "解释 gh aw compile 这条命令做了什么"` 先看懂它的作用。

### 步骤 4: 推送编译结果
```bash
git add .github/workflows/
git commit -m "chore: compile gh-aw workflow"
git push origin main
```

### 步骤 5: 手动触发工作流
- **方法 A（推荐）**：在 GitHub UI 页面。
  - 打开仓库 → **Actions** 标签页。
  - 左侧选择 **Tech Insight Workflow**。
  - 点击 **Run workflow** → **Run workflow**。
- **方法 B（CLI）**：
```bash
gh workflow run "Tech Insight Workflow"
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

> 💡 **试一试 · @github（让 Copilot 帮你看 PR）**

**练的能力**：`@github` 参与者 —— 回答仓库 / PR / issue 相关问题，可检索 GitHub。

**怎么做**：

1. 工作流跑完会出现一个 `[tech-insight]` 开头的 PR。
2. 在 Copilot Chat 把下面这句粘贴进去、回车：

```text
@github 总结最新这个 [tech-insight] PR 改了哪些文件、核心变更是什么、有没有需要注意的风险点？
```

**预期结果**：Copilot 概括该 PR 的 diff 要点（新增/更新了哪些报告与产物），帮你更快决定是否 **Merge**。

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

> 💡 **试一试 · Inline Chat（在编辑器里就地改代码）**

**练的能力**：Inline Chat —— 在光标/选区处直接对话改代码，不用切到侧栏，改完就地给 diff。

**怎么做**：

1. 打开 `frontend/styles.css`，选中配色相关的 CSS 变量那几行。
2. 按 Inline Chat（Windows/Linux `Ctrl+I`，macOS `Cmd+I`），把下面这句粘贴进去、回车，然后点 **Accept** 应用：

```text
把主色调改成深蓝（#1F3A5F），正文字号略增、行距加大一点，让报告更易读。只改这几个变量，别动其它样式。
```

**预期结果**：Copilot 直接在原处给出 CSS 改动；Accept 后刷新 `http://localhost:8000` 即见新配色——省去你自己查 CSS 属性名。

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

> 💡 **试一试 · 用 Chat 生成配置（cron 表达式）**

**练的能力**：用 Copilot Chat 生成你不熟的配置/语法 —— 这里是 GitHub Actions 的 cron。

**怎么做**：打开 Copilot Chat，把下面这句粘贴进去、回车：

```text
我要让 GitHub Actions 工作流每天「北京时间早上 5 点」运行，对应的 cron 表达式（UTC）是什么？请解释时区换算过程。
```

**预期结果**：Copilot 给出 `0 21 * * *` 并解释「北京 = UTC+8，5:00 − 8h = 前一天 21:00 UTC」。把它给的 cron 填进 `tech-insight.md` frontmatter 的 `schedule:` 下，再 `gh aw compile` 并推送即可。

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
│   ├── run_local_pipeline.py     # 本地诊断驱动（fallback，无需 Actions）
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
