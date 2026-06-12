# Frontend (GitHub Pages)

这是一个极简静态页面：在浏览器端把 `report.md` 渲染成可阅读的 HTML。

## 本地预览（零安装）

仓库根目录执行：

- `python3 -m http.server 8000 --directory Lab-01-Tech-Insights/frontend`
- 浏览器打开：`http://localhost:8000`

> 说明：直接双击打开 `index.html` 在部分浏览器会触发跨域限制，导致 `fetch(report.md)` 失败；用本地静态服务器即可。

## 使用方式

- 默认渲染：`report.md`（与 `index.html` 同目录）

## 部署到 GitHub Pages

本仓库使用 GitHub Pages 进行部署，无需额外的云服务。

### 开启方式

1. 打开仓库 → **Settings** → 左侧 **Pages**。
2. Source 选择 **GitHub Actions**。
3. 手动触发 `Deploy GitHub Pages` 工作流（`.github/workflows/deploy-pages.yml`）。

### 自动部署

当 `Lab-01-Tech-Insights/frontend/` 下的文件发生变更并推送到 `main` 分支时，`deploy-pages.yml` 会自动触发部署。

Tech Insight Workflow 每次运行后会将最新的 `report.md` 写入 `Lab-01-Tech-Insights/frontend/report.md`，从而自动触发 Pages 重新部署。

### 访问地址

部署成功后，访问：`https://<你的用户名>.github.io/<仓库名>/`

---

## 故障排查：`tech-insight` 工作流常见报错与修复

下面汇总了让 `tech-insight`（gh-aw，`engine: copilot`）端到端跑通过程中遇到的全部报错与修复，按出现顺序排列。改完工作流 frontmatter 后记得重新编译：`gh aw compile .github/workflows/tech-insight.md`。

### 前置条件（两个容易漏的开关）

1. **Copilot Token 权限**：`COPILOT_GITHUB_TOKEN` 必须是 **fine-grained PAT**，并在 **Permissions → Account permissions → Copilot Requests** 设为 **Read**（不是 Repository permissions 里的「Copilot agent settings」）。详见 `../README.md` 步骤 2。
2. **允许 Actions 建 PR**：**Settings → Actions → General → Workflow permissions** 勾选 **“Allow GitHub Actions to create and approve pull requests”**，否则 `create_pull_request` 会报 permission denied。

### 报错与修复对照

| 症状（日志关键字） | 根因 | 修复 |
| --- | --- | --- |
| `Authentication failed ... (HTTP 401)` / `models fetch returned 401` | PAT 缺 Copilot API 权限 | 给 fine-grained PAT 加 **Account → Copilot Requests = Read**，重新生成并更新 `COPILOT_GITHUB_TOKEN` secret |
| `ModuleNotFoundError: No module named 'httpx'` | runner 没装 MCP 脚本依赖 | frontmatter `steps:` 加 `actions/setup-python` + `pip install -r Lab-01-Tech-Insights/mcp-scripts/requirements.txt` |
| `{"error": "Expecting value: line 1 column 1"}` / `tech-cluster-or-fallback.sh ... exit code 1` | mcp-script wrapper 用 `echo $INPUT_X` 拼 JSON，含引号/反斜杠/`$`/`*` 的 payload 被 shell 搅烂成非法 JSON | wrapper 改为从 `os.environ` 取值、用子进程把 JSON 喂给脚本，彻底绕开 shell 拼接 |
| `CAPIError: 429 Maximum effective tokens exceeded (.../25000000)` | AWF 防火墙按「毛 token」累加，多轮重发大上下文很快触顶（该上限 frontmatter 不可调） | 压数据：`max_items_per_source` 25→3、`top_k` 12→6、summary 截断 320→100 |
| 同上但**偶发**（agent 时好时坏） | agent 偶尔把**文件路径**或空串当 JSON 传给工具，wrapper 硬崩 → 重试 → 触顶 | `_read_if_path()` 让解析**路径或内容都能吃**；wrapper 走带 `try/except` 的脚本，坏参数返回 `{"error"}` 而非崩溃，可自恢复 |
| `GitHub Actions is not permitted to create or approve pull requests` | 仓库默认不允许 Actions 建 PR | 打开上面「前置条件 2」的开关 |

> 经验：AWF 的「毛 token」上限（25M）和 gh-aw 自报的加权 `GH_AW_EFFECTIVE_TOKENS` 是两套计数。后者通常只有几 M；真正触顶的往往是**工具失败 → agent 重试 → 反复重发上下文**。所以「让工具稳定、不重试」比单纯砍数据更有效。

### 验证

```bash
gh workflow run "Tech Insight Workflow" --ref main
gh run watch
```

成功标志：日志无 `Maximum effective tokens exceeded`、cluster 无连续失败、`create_pull_request completed successfully`，Actions/PR 列表里出现 `[tech-insight] ...` 报告 PR。
