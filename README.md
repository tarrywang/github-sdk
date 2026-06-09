# Github-SDK-Workshop

本仓库包含多个可运行 Lab，当前主要内容如下：

- `Lab-01-Tech-Insights/`：基于新闻源的技术动态聚合与洞察 Lab
- `Lab-02-Podcast/`：基于爬虫 + GitHub Copilot 与 Microsoft Agent Framework 的《世界杯的每日播报》自动化播客生成 Lab
- `Lab-03-GitHub-Copilot/`：围绕 GitHub Copilot 与 Copilot SDK 的 PPT 生成 Lab

## Lab-01-Tech-Insights（你将做什么）

这是一个基于新闻源的「技术动态聚合与洞察」Lab：抓取多源更新 → 归一为信号 → 聚类热点 → 生成洞察与 Markdown 报告。

你将得到：
- `report.md`：一份可阅读的技术洞察报告（中文）
- `raw_signals.json` / `clusters/hotspots.json` / `insights/insights.json`：可回放的中间产物（便于调试与复现实验）

- 入口文档：`Lab-01-Tech-Insights/README.md`
- 工作流文件：`.github/workflows/tech-insight.md`

最短触发路径（手动触发）：

```bash
# 编译 gh-aw 工作流（需要 gh-aw 扩展）
gh aw compile .github/workflows/tech-insight.md

# 在 GitHub Actions UI 中手动触发，或：
gh workflow run tech-insight
```

> 说明：`.github/workflows` 在仓库根目录（GitHub Actions 规范要求）。报告会自动部署到 GitHub Pages。

## Lab-02-Podcast（你将做什么）

这是一个基于爬虫 + GitHub Copilot 与 Microsoft Agent Framework (MAF) 的「自动化播客生成」Lab，节目名为《世界杯的每日播报》：先用内置爬虫从央视体育抓取 5 条最新的美加墨世界杯新闻并提取正文，再通过 MAF Workflow 编排三个 Agent 串联生成双人对谈风格的播客内容，并每日定时触发、提交结果。

你将体验：
- 使用 Python 标准库内置爬虫从 CCTV 抓取最新美加墨世界杯新闻并提取正文
- 使用 GitHub Copilot 作为 LLM 提供方，结合 MAF Workflow 编排三个 Agent（爬取+大纲 → 脚本 → 润色）生成双人对谈播客内容
- 通过 GitHub Actions 实现每日自动调度与内容发布

你将得到：
- `podcast/` 目录下生成的《世界杯的每日播报》播客内容文件
- 一套可本地运行也可托管于 GitHub Actions 的完整自动化流程

- 入口文档：`Lab-02-Podcast/README.md`
- 本地运行：先 `cd Lab-02-Podcast`，安装依赖后直接执行（无需传入话题，脚本会自动爬取当日新闻）：

```bash
cd Lab-02-Podcast
pip install -r requirements.txt --pre
python podcast_workflow.py
```

### 通过 GitHub Actions 触发

如果你希望通过 GitHub Actions 自动运行播客生成工作流，请按以下步骤操作：

1. **Fork 本仓库**到你自己的 GitHub 账号下
2. **创建 Fine-grained Personal Access Token**：
   - 前往 [GitHub Personal Access Tokens](https://github.com/settings/personal-access-tokens) 页面
   - 点击 **Generate new token**，选择 **Fine-grained personal access tokens**
   - 在权限设置中，添加 **Copilot** → **Copilot requests** 权限（Read and Write）
   - 生成并复制 Token
3. **添加 Repository Secret**：
   - 进入你 Fork 后的仓库，打开 **Settings** → **Secrets and variables** → **Actions**
   - 点击 **New repository secret**
   - Name 填写 `COPILOT_GITHUB_TOKEN`，Value 粘贴上一步生成的 Token
4. 在 **Actions** 页面手动触发 `Daily Podcast Generator` 工作流，或等待每日定时调度

## Lab-03-GitHub-Copilot（你将做什么）

这是一个用于学习 GitHub Copilot 与 Copilot SDK 的 Lab，聚焦“把网页内容生成为 PowerPoint”。

你将体验两个场景：
- 在 VS Code 聊天窗口中，通过自然语言触发 `url2ppt` 和 `pptx` skill，把单个网页 URL 直接转换为 PPT
- 在 Next.js Web 应用中，由前端发起请求、后端通过 Copilot SDK 生成 PPT，并将进度流式返回给页面

你将得到：
- 一份由网页内容整理生成的 `.pptx` 演示文稿
- 一个可本地运行的 Copilot SDK 示例 Web 应用

- 入口文档：`Lab-03-GitHub-Copilot/README.md`
- 本地运行：先 `cd Lab-03-GitHub-Copilot`，复制 `.env.example` 为 `.env` 并填写 `COPILOT_GITHUB_TOKEN`，然后执行 `npm install` 和 `npm run dev`
- 默认访问地址：`http://localhost:3000`

最短本地启动：

```bash
cd Lab-03-GitHub-Copilot
cp .env.example .env
# 填写 COPILOT_GITHUB_TOKEN 后继续
npm install
npm run dev
```
