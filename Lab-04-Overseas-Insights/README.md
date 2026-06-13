# Lab-04 · 出海市场洞察（Overseas Market Insight）

一个基于 **GitHub Agentic Workflow（gh-aw）** 的每日跨境电商出海市场调查工作流。每天**北京时间早上 5 点**自动生成一份
聚焦 **美妆护肤 / 3C电子 / 饰品配饰** 三大品类、覆盖 **北美 / 欧洲 / 东南亚 / 全球** 市场的热点话题、热门产品与趋势分析报告。

> 架构沿用 `Lab-01-Tech-Insights`，但数据策略以**联网深度研究为主**：RSS 种子源作为可靠基线，agent 在白名单内多轮联网抓取并交叉验证，综合产出报告。

## 架构与数据流

```
种子源 (input/api/source_list.json · 按品类×市场打标)
    ↓ 阶段1：基线抓取（RSS）         mcp-scripts (Python: httpx)
    ↓ raw_signals.json
    ↓ 阶段1.5：深度联网研究合并        Copilot agent（白名单内 web 抓取 + 交叉验证）
    ↓ 阶段2：聚类（分品类/分市场）      LLM + overseas_cluster_or_fallback
    ↓ output/clusters/hotspots.json
    ↓ 阶段3：洞察生成                 LLM + overseas_insight_or_fallback
    ↓ output/insights/insights.json
    ↓ 阶段4：报告生成                 LLM + overseas_render_report_or_fallback
    ↓ output/report.md + frontend/report.md
    ↓ safe-outputs 自动创建 PR
合并 PR → deploy-pages 自动部署
    ↓
GitHub Pages（/overseas/ 在线查看）
```

每个阶段都有 LLM + 确定性兜底（`*_or_fallback`）：无 LLM 或 LLM 输出不可解析时，自动退化为可用的兜底报告。

## 目录结构

```
Lab-04-Overseas-Insights/
├── input/api/source_list.json   # 种子源（category=beauty|3c|jewelry, markets=na|eu|sea|global, fetchable=rss|research-only）
├── mcp-scripts/                 # Python 工具（fetch/parse/cluster/insight/render，含兜底）
├── frontend/                    # 静态页面（浏览器端渲染 report.md），发布到 Pages /overseas/
├── output/                      # 运行产物（gitignored）：raw_signals/clusters/insights/report
├── run_local_pipeline.py        # 本地兜底诊断驱动（无需 token / LLM）
└── requirements.txt
```

## 报告结构

今日摘要 → 热点话题（分品类）→ 热门产品 / 潜力爆品（分品类表格：产品/市场/价格带/核心卖点/来源）→
分市场速览（北美/欧洲/东南亚/全球）→ 选品与营销行动建议 → 风险与合规提示 → 数据来源。

## 本地验证（无需 token / LLM）

从仓库根目录运行，触发各阶段的确定性兜底逻辑，验证整条工具链：

```bash
python3 -m venv .venv
.venv/bin/pip install -r Lab-04-Overseas-Insights/requirements.txt
.venv/bin/python Lab-04-Overseas-Insights/run_local_pipeline.py
```

产物：`output/{raw_signals.json, clusters/hotspots.json, insights/insights.json, report.md}` 及 `frontend/report.md`。
`raw_signals.json` 中每条 item 的 `tracks` 应包含品类（如 `beauty`）与市场（如 `market:na`）标签。

## 工作流（GitHub Actions）

- 源文件：`.github/workflows/overseas-insight.md`（gh-aw 格式：frontmatter + 中文 prompt）。
- 编译：改完 `.md` 后必须运行 `gh aw compile .github/workflows/overseas-insight.md` 重新生成 `overseas-insight.lock.yml`（Actions 实际运行的是 lock 文件）。
- 触发：每天 `cron: "0 21 * * *"`（UTC 21:00 = 北京时间次日 05:00），并保留 `workflow_dispatch` 手动触发。
- Secret：复用 `COPILOT_GITHUB_TOKEN`（fine-grained PAT，Account → Copilot Requests = Read）。
- 输出：通过 safe-outputs 创建标题前缀 `[overseas-insight]` 的 PR。

手动触发与查看：

```bash
gh workflow run "Overseas Insight Workflow" --ref main
gh run watch
```

## 数据源说明（诚实的局限）

- **RSS 基线**（`fetchable: rss`）：行业/贸易媒体的 RSS/Atom，在白名单内可稳定抓取。
- **research-only**（`fetchable: research-only`）：Amazon Best Sellers / TikTok Shop / Google Trends 等存在反爬或 JS 渲染，沙箱内常被拦截。
  这些「热品榜单」信号主要**通过贸易媒体的报道二次综合**得到，而非直接抓取；目标不可达时报告会注明缺口并以 RSS 基线兜底。
- 新增联网研究域名需同时加入 `overseas-insight.md` 的 `network.allowed` 并重新 `gh aw compile`。
