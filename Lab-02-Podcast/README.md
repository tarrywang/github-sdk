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

2. 安装依赖：
```bash
pip install -r requirements.txt --pre
```

3. 配置环境变量（可选）：
```bash
cp .env.example .env
# 编辑 .env 文件，配置 GitHub Copilot 相关变量
```

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
python podcast_workflow.py
```

## 工作流程

1. **爬取新闻并生成大纲**：`PodcastSearchExecutor` 从 CCTV 体育频道爬取 5 条最新美加墨世界杯新闻并读取正文，再调用 GitHub Copilot 基于真实内容生成播客大纲
2. **脚本撰写**：`PodcastContentExecutor` 调用 GitHub Copilot 生成两人对话风格脚本
3. **润色保存**：`PodcastScriptExecutor` 调用 GitHub Copilot 润色脚本并保存至 `podcast/` 目录

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
