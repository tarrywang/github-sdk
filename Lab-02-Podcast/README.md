# 播客工作流

基于 Microsoft Agent Framework (MAF) 与 GitHub Copilot 的自动化播客生成系统。该工作流通过 MAF Workflow 编排三个 Agent，使用 GitHub Copilot 作为 LLM 提供方，自动生成《世界杯的每日播报》播客内容。

## 功能特性

- **GitHub Copilot 驱动**：使用 `GitHubCopilotAgent` 作为 LLM 提供方，无需 Azure AI Foundry 资源
- **MAF Workflow 编排**：使用 `WorkflowBuilder` 构建顺序执行的多 Agent 工作流
- **三 Agent 串联**：爬取新闻生成大纲 → 内容生成脚本 → 润色并保存最终脚本
- **新闻爬虫**：从 CCTV 体育频道抓取最新美加墨世界杯新闻并提取正文，基于真实内容生成大纲
- **流式事件输出**：实时输出工作流执行进度

## 架构说明

```
WorkflowBuilder 顺序工作流：

┌─────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│ PodcastSearchExecutor│───▶│PodcastContentExecutor│───▶│PodcastScriptExecutor │
│  (podcast-search-   │    │  (podcast-content-   │    │  (podcast-script-    │
│   agent)             │    │   agent)              │    │   agent)              │
│                     │    │                      │    │                      │
│ 爬取世界杯新闻并生成 │    │ 根据大纲生成脚本草稿  │    │ 润色并保存最终脚本    │
│ 大纲                 │    │                      │    │                      │
└─────────────────────┘    └──────────────────────┘    └──────────────────────┘
         ▲                                                        │
         │                                                        ▼
    用户输入主题                                          yield_output(最终脚本)
```

每个 Executor 内部封装一个 `GitHubCopilotAgent` 实例，通过 `ctx.send_message()` 在 Executor 之间传递数据，最终由 `ctx.yield_output()` 输出工作流结果。

> 💡 **试一试 · @workspace（让 Copilot 读懂整个工作流）**

**练的能力**：`@workspace` 参与者 —— Copilot 会检索整个项目来回答，适合快速看懂陌生代码的结构与数据流。

**怎么做**：

1. 在 VS Code 打开本目录，打开 Copilot Chat（Windows/Linux `Ctrl+Alt+I`，macOS `Ctrl+Cmd+I`）。
2. 把下面这段问题复制粘贴进 Chat 输入框、回车；看完想深入可继续追问（如「这三个 Executor 各调用了几次 GitHub Copilot、分别用什么 system instruction？」）。

```text
@workspace podcast_workflow.py 是如何用 WorkflowBuilder 把三个 Executor（搜索/内容/脚本）串成顺序工作流的？数据在它们之间是怎么传递的？
```

**预期结果**：Copilot 会描述 search → content → script 的串联关系，并点名 `ctx.send_message()` / `ctx.yield_output()` 等传递方式，几分钟带你看懂全局。

> 顺手练「提示工程」：让它对比三个 `GitHubCopilotAgent` 的 system instructions（搜索 / 撰稿 / 润色三种人设），体会「角色一致性」是怎么写进系统提示词的。

## 前置条件

- Python 3.11+
- GitHub Copilot CLI：已安装并完成认证（通过 `gh auth login`）
- GitHub Copilot 订阅：有效的 GitHub Copilot 订阅

## 安装步骤

1. 克隆仓库：
```bash
git clone <你的仓库地址>
cd github-sdk/Lab-02-Podcast
```

2. 创建并激活虚拟环境（**本地 Python 版本过低、又不便全局升级时必看**）。本项目需 Python **3.11+**；若你的 `python3` 低于 3.11、又因其他项目依赖不便全局升级，**不要动全局 Python**，改用「另装新版 + 单独建虚拟环境」，两者互不影响：
```bash
# ① 另装一个新版 Python（与旧版共存，不覆盖）
#    macOS：       brew install python@3.11
#    Windows：     到 python.org 下载 3.11 安装包，安装时勾选「Add python.exe to PATH」
#    跨平台多版本： pyenv install 3.11.9

# ② 用新版创建虚拟环境（关键：显式写 python3.11 而非默认 python3；
#    venv 会继承创建它的那个解释器的版本）
# macOS / Linux：
python3.11 -m venv .venv && source .venv/bin/activate
# Windows（PowerShell）：
#   py -3.11 -m venv .venv; .venv\Scripts\Activate.ps1

# ③ 确认已是新版；退出环境用 deactivate（.venv/ 已在仓库 .gitignore 中）
python --version   # 应显示 3.11.x
```
> 若你的 `python3` 本就 ≥ 3.11，可直接 `python3 -m venv .venv` 省去第 ① 步。

3. 安装依赖（在已激活的虚拟环境中）：
```bash
pip install -r requirements.txt --pre
```

4. 配置环境变量（可选）：
```bash
cp .env.example .env
# 编辑 .env 文件，配置 GitHub Copilot 相关变量
```

> 💡 **试一试 · GitHub Copilot CLI（终端里的 AI 助手）**

**练的能力**：新版独立 **Copilot CLI** —— 终端里的交互式 agent，可 `copilot` 交互、`copilot -p "..."` 非交互；记不住跨平台命令时让它给。

**怎么做**：

1. 安装（需 Node.js，只需一次）：`npm install -g @github/copilot`（或首次运行 `gh copilot`，gh 会自动下载并透传到它）。
2. 在终端让它给「创建并激活虚拟环境」的命令：

```bash
copilot -p "给我在 Windows 上创建并激活一个 python 虚拟环境的命令"
```

**预期结果**：通常给出 `python -m venv .venv` 加 `.venv\Scripts\activate`（macOS / Linux 则是 `source .venv/bin/activate`）。想多轮对话就直接运行 `copilot`。装依赖报错时，也可把报错贴进 VS Code Copilot Chat 问「`@terminal` 这个报错怎么解决？」。

## 配置说明

### GitHub Copilot 配置

以下环境变量可在 `.env` 中配置：

| 变量名 | 说明 | 默认值 |
|---|---|---|
| `GITHUB_COPILOT_MODEL` | 使用的模型（如 `gpt-5.4`） | `gpt-5.4` |
| `GITHUB_COPILOT_TIMEOUT` | 请求超时（秒） | `60` |
| `GITHUB_COPILOT_LOG_LEVEL` | CLI 日志级别 | `info` |

## 使用方式

使用默认主题运行工作流：
```bash
python Lab-02-Podcast/podcast_workflow.py
```

> 💡 **试一试 · Copilot Edits（Edit 模式）**

**练的能力**：Copilot Edits（也叫 Edit 模式）—— 让 Copilot 按你的描述直接改代码，但先给出 **diff** 由你逐处 Accept / Discard，安全可控。

**怎么做**：

1. 在 VS Code 打开 `podcast_workflow.py`，选中 `crawl_world_cup_news` 里 `asyncio.gather(...)` 那几行。
2. 打开 Copilot Chat（Windows/Linux `Ctrl+Alt+I`，macOS `Ctrl+Cmd+I`），在输入框上方把模式由 **Ask** 切到 **Edit**。
3. 把下面这段提示词粘贴进去回车，然后逐处审阅 **diff**、点 **Accept** 应用：

```text
为选中的 asyncio.gather 加上 return_exceptions=True，并给每条 fetch_article 增加 10 秒超时。
任一条抓取失败或超时都不要中断整体，只跳过该条并打印一行警告日志，其余逻辑保持不变。
```

**预期结果**：`asyncio.gather(...)` 被改成带 `return_exceptions=True` 并加了超时；之后某条新闻抓取失败时，播客流水线不会整体崩溃，只跳过那一条。

> 顺手练斜杠命令：选中 `crawl_world_cup_news`，在 Inline Chat（Win `Ctrl+I` / mac `Cmd+I`）输入 `/doc`，自动生成规范的中文 docstring。

## 工作流程

1. **爬取新闻并生成大纲**：`PodcastSearchExecutor` 从 CCTV 体育频道爬取 5 条最新美加墨世界杯新闻并读取正文，再调用 GitHub Copilot 基于真实内容生成播客大纲
2. **脚本撰写**：`PodcastContentExecutor` 调用 GitHub Copilot 生成两人对话风格脚本
3. **润色保存**：`PodcastScriptExecutor` 调用 GitHub Copilot 润色脚本并保存至 `podcast/` 目录

> 💡 **试一试 · 斜杠命令 /explain 与 /tests**

**练的能力**：Chat 斜杠命令 —— `/explain` 解释选中代码，`/tests` 为它生成单元测试。

**怎么做**：

1. 打开 `podcast_workflow.py`，选中正则 `ARTICLE_URL_PATTERN`。
2. Inline Chat（Windows/Linux `Ctrl+I`，macOS `Cmd+I`）里粘贴下面这句、回车；看懂后保持选中，再输入 `/tests` 生成测试：

```text
/explain 这个正则匹配什么样的 URL？请给 3 个能匹配、3 个不能匹配的例子。
```

**预期结果**：Copilot 会拆解正则各部分并举正反例；`/tests` 通常会生成一组 `pytest` 用例（记得人工核对断言是否正确）。

> 💡 **试一试 · Agent 模式（自主多步改造）**

**练的能力**：Agent 模式 —— 给一个较大目标，Copilot 自主跨多文件 / 多步完成（改代码、跑命令），有风险的命令会先征求你同意。

**怎么做**：

1. 打开 Copilot Chat，把模式切到 **Agent**（Windows/Linux `Ctrl+Shift+I`，macOS `Shift+Cmd+I`）。
2. 把下面的目标粘贴进去回车；Copilot 会列出计划并逐步执行，要跑命令时会停下来等你确认：

```text
CCTV 体育页面的 HTML 结构可能已变化。请检查并更新 ListParser 与 ArticleParser 的解析逻辑，
使 crawl_world_cup_news 仍能正确抓到新闻列表与正文，并补一个最小自测来验证解析结果。
```

**预期结果**：它会跨 `ListParser`、`ArticleParser` 等处自主修改并给出验证；你全程审阅每一步，不满意可随时打断。

> 📚 以上各步骤穿插的 Copilot 用法，更系统的版本（含 Windows / macOS 快捷键对照、功能覆盖地图）见仓库根目录《GitHub SDK Workshop 用户操作手册》。

## 项目结构

```
Lab-02-Podcast/
├── .env.example                  # 环境变量模板
├── .env                          # 环境变量（本地）
├── podcast/                      # 生成的播客内容
│   └── 2p_podcast_<uuid>.txt
├── podcast_workflow.py          # 主工作流脚本（爬虫 + MAF Workflow + GitHub Copilot）
├── requirements.txt             # Python 依赖
└── README.md
```

## 生成内容说明

播客文件保存在 `podcast/` 目录下，以唯一标识符命名：
- 格式：`2p_podcast_<uuid>.txt`
- 内容：由 AI 生成的两位主持人（Host / Guest）围绕话题的对话内容

## 关键技术

- **[Microsoft Agent Framework (MAF)](https://github.com/microsoft/agent-framework)**：提供 `Executor`、`WorkflowBuilder`、`WorkflowContext` 等核心抽象，用于构建多 Agent 工作流
- **[GitHubCopilotAgent](https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/providers/github_copilot)**：MAF 提供的 GitHub Copilot LLM 适配器，通过 Copilot CLI 调用模型
- **Workflow 模式**：基于 MAF 的 `WorkflowBuilder` 构建顺序执行图，通过 `ctx.send_message()` 传递中间结果，`ctx.yield_output()` 产出最终结果

## 常见问题排查

### GitHub Copilot CLI

确保已安装 GitHub Copilot CLI 并完成认证：
```bash
# 检查 CLI 是否可用
copilot --version

# 如需指定 CLI 路径，设置环境变量
export GITHUB_COPILOT_CLI_PATH=/path/to/copilot
```

### 超时问题

如果生成长篇脚本时出现超时错误，可在 `.env` 中增大超时值：
```
GITHUB_COPILOT_TIMEOUT = 180
```

### 认证问题

确保 GitHub Copilot 订阅有效，且 CLI 已通过 `gh auth login` 认证。

## 许可证

MIT License

## 致谢

本项目基于以下技术构建：
- [Microsoft Agent Framework (MAF)](https://github.com/microsoft/agent-framework)
- [GitHub Copilot](https://github.com/features/copilot)
