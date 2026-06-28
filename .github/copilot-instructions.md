# GitHub Copilot 仓库自定义指令

> 本文件是 GitHub Copilot 的「仓库级自定义指令」（repository custom instructions）。
> Copilot 在本仓库回答问题或生成代码时会自动参考这里的内容，无需每次手动粘贴背景。
> 它同时是 Workshop 教材第 3 章「自定义指令」的活教材，请保持内容真实、简洁、可执行。

## 这个仓库是什么

GitHub SDK Workshop —— 一个面向学员的多 Lab 动手实验仓库，核心是「GitHub Agentic Workflows（gh-aw）」
与「GitHub Copilot」驱动的 AI 自动化。包含：

- **Lab-01-Tech-Insights/** — 基于 gh-aw 的 EV 市场洞察流水线（Python + MCP Scripts，`engine: copilot`）。
- **Lab-02-Podcast/** — 基于 Microsoft Agent Framework（MAF）+ GitHub Copilot 的播客生成（Python，三 Executor 顺序工作流）。
- **Lab-03-GitHub-Copilot/** — 基于 Copilot SDK 的「网页转 PPT」（Next.js + TypeScript）。
- **Lab-04-Overseas-Insights/** — 在 Lab-01 架构上扩展的「出海市场洞察」（gh-aw，美妆护肤·北美）。

## 技术栈与约定

- **语言**：Lab-01 / Lab-02 / Lab-04 为 Python 3.10+（Lab-02 需 3.11+）；Lab-03 为 Node.js + TypeScript（Next.js）。
- **Python 风格**：标准库优先、`from __future__ import annotations`、`dataclass`、`pathlib.Path`、类型注解；保持与现有 `tech_insight_tools.py` 一致的命名与结构。
- **面向 LLM 的提示词一律用中文**；报告正文以中文为主。
- **gh-aw 工作流**：源文件是 `.github/workflows/*.md`（YAML frontmatter + 中文指令）。
  **修改 `.md` 后必须运行 `gh aw compile <file>` 重新生成 `*.lock.yml`** —— GitHub Actions 实际运行的是 lock 文件。
- **产出走 safe-outputs**：工作流不直接写仓库，而是自动创建 Pull Request；不要在工作流里引入手工 git 流程。
- **网络白名单**：gh-aw 在 squid 防火墙容器内运行，联网只能访问 frontmatter `network.allowed` 列出的域名；新增域名后需重新 `gh aw compile`。
- **token 预算**：gh-aw 运行环境对累计「毛 token」有 **25M 硬上限（不可调）**。深度联网研究/大上下文若不受限会触顶导致整轮失败 —— 生成相关代码或提示词时务必控制抓取页数与单页读取长度。
- **运行产物 `output/` 已在 `.gitignore` 中**；`frontend/report.md` 是被跟踪的展示文件。

## 目录速览

- `.github/workflows/tech-insight.md` / `overseas-insight.md` — gh-aw 工作流定义（+ 对应 `.lock.yml`）。
- `Lab-01-Tech-Insights/mcp-scripts/` — Python 工具（fetch / load / cluster / insight / render，均带 `*_or_fallback` 确定性兜底）。
- `Lab-02-Podcast/podcast_workflow.py` — 爬虫 + MAF `WorkflowBuilder` + 三个 `GitHubCopilotAgent`。
- `Lab-0x/frontend/` — 浏览器端把 `report.md` 渲染为 HTML 的静态页面。

## 回答与生成代码时请遵循

- 优先复用现有函数与模式（如 `*_or_fallback` 兜底、`_derive_tracks` 的数据驱动标签），不要另起炉灶。
- 改动尽量小而精准，只触及必要文件；遵循各 Lab 既有目录与命名约定。
- 涉及 gh-aw 时，提醒「改 `.md` → `gh aw compile` → 推送」的完整链路。
- 给出的命令使用仓库根目录相对路径，不要写绝对路径。
