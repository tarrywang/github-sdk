# Prerequisites

完成本仓库所有 Lab 所需的软件与账号。

## 账号

| 账号 | 用途 | 涉及 Lab |
|------|------|----------|
| GitHub（含 Copilot 订阅） | gh-aw 引擎、Copilot Chat、Copilot SDK | Lab-01, Lab-03 |
| Azure（含 AI Projects 订阅） | 播客生成 Agent | Lab-02 |

## 软件

| 软件 | 最低版本 | 涉及 Lab | 安装 |
|------|---------|----------|------|
| Git | 2.x | 全部 | https://git-scm.com |
| GitHub CLI (`gh`) | 2.x | Lab-01 | https://cli.github.com |
| gh-aw 扩展 | latest | Lab-01 | `gh extension install github/gh-aw` |
| Python | 3.11+ | Lab-01, Lab-02 | https://www.python.org |
| Node.js | 24+ | Lab-03 | https://nodejs.org |
| VS Code | latest | 全部（推荐） | https://code.visualstudio.com |
| VS Code GitHub Copilot 扩展 | latest | Lab-03 | VS Code 扩展市场搜索 `GitHub Copilot` |
| Azure CLI (`az`) | 2.x | Lab-02 | https://learn.microsoft.com/cli/azure/install-azure-cli |

## 快速验证

```bash
git --version          # >= 2.x
gh --version           # >= 2.x
gh aw --version        # 已安装即可
python3 --version      # >= 3.11
node --version         # >= 24
code --version         # 已安装即可
az --version           # >= 2.x（仅 Lab-02）
```

## 用 GitHub Copilot 加速搭建

> 💡 装好 Node.js 后，可装上**新版 GitHub Copilot CLI**（终端里的 AI 助手）：`npm install -g @github/copilot`
> （首次运行 `gh copilot` 也会自动下载并透传到它）。忘了某个工具的安装命令，就 `copilot -p "给我在 Windows 用 winget 安装 GitHub CLI 的命令"`；
> 想多轮对话就直接运行 `copilot` 进交互会话。安装或认证报错时，也可把输出贴进 VS Code Copilot Chat 问「@terminal 这个报错怎么解决？」。
> 注意 VS Code 的 Copilot 快捷键在 Windows/Linux 与 macOS 上不同（如 Inline Chat：Windows/Linux `Ctrl+I`、macOS `Cmd+I`）。完整用法见仓库根目录《GitHub SDK Workshop 用户操作手册》第 3 章。
