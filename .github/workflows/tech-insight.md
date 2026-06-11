---
name: Tech Insight Workflow
on:
  workflow_dispatch:
strict: false
permissions:
  contents: read
tools:
  bash: [":*"]
  edit:
engine: copilot
timeout-minutes: 45
steps:
  - name: Set up Python
    uses: actions/setup-python@v5
    with:
      python-version: '3.11'
  - name: Install Python deps for mcp-scripts
    run: |
      python3 -m pip install --upgrade pip
      python3 -m pip install -r Lab-01-Tech-Insights/mcp-scripts/requirements.txt
network:
  allowed:
    - defaults
    - python
    - "openai.com"
    - "github.blog"
    - "devblogs.microsoft.com"
    - "blog.google"
    - "aws.amazon.com"
    - "blogs.nvidia.com"
    - "developer.apple.com"
    - "blog.cloudflare.com"
    - "deepmind.google"
    - "huggingface.co"
    - "news.ycombinator.com"
    - "www.producthunt.com"
    - "techcrunch.com"
    - "www.theverge.com"
    - "feeds.arstechnica.com"
    - "www.wired.com"
    - "www.technologyreview.com"
    - "feed.infoq.com"
    - "www.infoq.com"
    - "lobste.rs"
    - "dev.to"
safe-outputs:
  create-pull-request:
    title-prefix: "[tech-insight] "
    labels: [automation, tech-insight]
mcp-scripts:
  tech-read-source-list:
    description: "Read RSS source list configuration"
    inputs:
      source_list_path:
        type: string
        required: true
    run: |
      cd "$GITHUB_WORKSPACE"
      echo "{\"source_list_path\": \"$INPUT_SOURCE_LIST_PATH\"}" | python3 Lab-01-Tech-Insights/mcp-scripts/tech_read_source_list.py
  tech-fetch-all-to-disk:
    description: "Fetch all sources to disk in parallel"
    inputs:
      source_list_path:
        type: string
        required: true
      signals_dir:
        type: string
        required: true
      timeout_seconds:
        type: number
        default: 15
      max_chars:
        type: number
        default: 200000
      max_items_per_source:
        type: number
        default: 3
    timeout: 300
    run: |
      cd "$GITHUB_WORKSPACE"
      python3 -c "
      import json, sys
      sys.path.insert(0, 'Lab-01-Tech-Insights/mcp-scripts')
      from tech_insight_tools import tech_fetch_all_to_disk
      result = tech_fetch_all_to_disk(
          source_list_path='$INPUT_SOURCE_LIST_PATH',
          signals_dir='$INPUT_SIGNALS_DIR',
          timeout_seconds=int('${INPUT_TIMEOUT_SECONDS:-15}'),
          max_chars=int('${INPUT_MAX_CHARS:-200000}'),
          max_items_per_source=int('${INPUT_MAX_ITEMS_PER_SOURCE:-3}')
      )
      print(json.dumps(result, ensure_ascii=False, default=str))
      "
  tech-load-articles-from-disk:
    description: "Load and filter valid articles from disk"
    inputs:
      signals_dir:
        type: string
        required: true
      source_list_path:
        type: string
        required: true
      max_items_per_source:
        type: number
        default: 3
      time_window_hours:
        type: number
        default: 24
    run: |
      cd "$GITHUB_WORKSPACE"
      python3 -c "
      import json, sys
      sys.path.insert(0, 'Lab-01-Tech-Insights/mcp-scripts')
      from tech_insight_tools import tech_load_articles_from_disk
      result = tech_load_articles_from_disk(
          signals_dir='$INPUT_SIGNALS_DIR',
          source_list_path='$INPUT_SOURCE_LIST_PATH',
          max_items_per_source=int('${INPUT_MAX_ITEMS_PER_SOURCE:-3}'),
          time_window_hours=int('${INPUT_TIME_WINDOW_HOURS:-24}')
      )
      print(json.dumps(result, ensure_ascii=False, default=str))
      "
  tech-cluster-or-fallback:
    description: "Validate and fallback clustering results"
    inputs:
      raw_signals_json:
        type: string
        required: true
      clusters_json:
        type: string
        required: true
      top_k:
        type: number
        default: 6
    run: |
      cd "$GITHUB_WORKSPACE"
      python3 -c "import os, json, sys, subprocess; payload = json.dumps({'raw_signals_json': os.environ.get('INPUT_RAW_SIGNALS_JSON', ''), 'clusters_json': os.environ.get('INPUT_CLUSTERS_JSON', ''), 'top_k': int(os.environ.get('INPUT_TOP_K') or 6)}); sys.exit(subprocess.run([sys.executable, 'Lab-01-Tech-Insights/mcp-scripts/tech_cluster_or_fallback.py'], input=payload, text=True).returncode)"
  tech-insight-or-fallback:
    description: "Validate and fallback insight results"
    inputs:
      clusters_json:
        type: string
        required: true
      insights_json:
        type: string
        required: true
    run: |
      cd "$GITHUB_WORKSPACE"
      python3 -c "import os, json, sys, subprocess; payload = json.dumps({'clusters_json': os.environ.get('INPUT_CLUSTERS_JSON', ''), 'insights_json': os.environ.get('INPUT_INSIGHTS_JSON', '')}); sys.exit(subprocess.run([sys.executable, 'Lab-01-Tech-Insights/mcp-scripts/tech_insight_or_fallback.py'], input=payload, text=True).returncode)"
  tech-render-report-or-fallback:
    description: "Validate and fallback report rendering"
    inputs:
      clusters_json:
        type: string
        required: true
      insights_json:
        type: string
        required: true
      draft_markdown:
        type: string
        required: true
    run: |
      cd "$GITHUB_WORKSPACE"
      python3 -c "import os, json, sys, subprocess; payload = json.dumps({'clusters_json': os.environ.get('INPUT_CLUSTERS_JSON', ''), 'insights_json': os.environ.get('INPUT_INSIGHTS_JSON', ''), 'draft_markdown': os.environ.get('INPUT_DRAFT_MARKDOWN', '')}); sys.exit(subprocess.run([sys.executable, 'Lab-01-Tech-Insights/mcp-scripts/tech_render_report_or_fallback.py'], input=payload, text=True).returncode)"
  write-text-file:
    description: "Write text content to a file"
    inputs:
      path:
        type: string
        required: true
      text:
        type: string
        required: true
      overwrite:
        type: boolean
        default: true
    run: |
      cd "$GITHUB_WORKSPACE"
      python3 -c "import os, json, sys, subprocess; payload = json.dumps({'path': os.environ.get('INPUT_PATH', ''), 'text': os.environ.get('INPUT_TEXT', ''), 'overwrite': os.environ.get('INPUT_OVERWRITE', 'true').strip().lower() not in ('false', '0', 'no')}); sys.exit(subprocess.run([sys.executable, 'Lab-01-Tech-Insights/mcp-scripts/write_text_file.py'], input=payload, text=True).returncode)"
---

# Tech Insight 工作流

目标：以仓库根目录相对路径运行 Lab-01 Tech Insights 主流程，替代原有 MAF/Azure 工作流编排；只允许手动触发，不要添加 `schedule` 或任何其他触发器。

默认配置如下：

- `source_list_path`: `Lab-01-Tech-Insights/input/api/rss_list.json`
- `signals_dir`: `Lab-01-Tech-Insights/output/signals`
- `output_dir`: `Lab-01-Tech-Insights/output`
- `time_window_hours`: `24`
- `top_k`: `6`
- `max_items_per_source`: `3`
- `timeout_seconds`: `15`
- `max_chars`: `200000`

执行约束：

- 全程只使用仓库根目录相对路径，不要写绝对路径。
- 不要增加任何原流程之外的能力，不要混入 social insight 内容。
- 所有面向模型的提示词必须使用中文，并严格沿用原工作流里的中文提示原文。
- 关键中间产物必须落盘：`raw_signals.json`、`clusters/hotspots.json`、`insights/insights.json`、`report.md`。
- 最终除写入 `Lab-01-Tech-Insights/output/report.md` 外，还要把同一份 Markdown 写入 `Lab-01-Tech-Insights/frontend/report.md`，并通过 safe-outputs 的提交机制提交 `Lab-01-Tech-Insights/frontend/report.md`。

## 阶段 1：抓取并装载原始信号

1. 先调用 `tech.read_source_list(source_list_path)` 读取并确认源列表可用。
2. 调用 `tech.fetch_all_to_disk(source_list_path, signals_dir, timeout_seconds=15, max_chars=200000, max_items_per_source=3)` 抓取所有信号并落盘到 `signals_dir`。
3. 调用 `tech.load_articles_from_disk(signals_dir, source_list_path, max_items_per_source=3, time_window_hours=24)` 生成原始信号 JSON。
4. 用 `edit` 工具将原始信号 JSON 写入 `Lab-01-Tech-Insights/output/raw_signals.json`。
5. 简要汇报源列表路径、抓取目录、纳入时间窗与原始信号保存位置。
6. 如果工具提示使用了兜底逻辑，在输出中注明。

## 阶段 2：聚类趋势与重点更新

1. 基于阶段 1 的原始信号，按下面这段中文提示原文构造聚类请求；必须保留原文语义与结构，仅把占位符替换成实际值与实际 JSON：

```text
你是 Tech Hotspot Clustering Agent。
任务：把过去 {Local.TimeWindowHours} 小时内的文章信号聚合成可行动的主题/更新列表。

## 输入（严格 JSON）
{MessageText(Local.RawSignals)}

## 聚类原则（混合）
- 先利用结构化元数据分桶：company / signal_level / source_type / include_keywords 派生标签
- 再在桶内按主题合并（标题 + 摘要 + 链接域名）
- 需要同时保留两类输出：
  1) cross_source_trends：多来源共振的趋势主题（coverage 高）
  2) high_signal_singles：单来源但信号强（S/A 或官方更新/Release）的重要更新

## 强约束
- 必须输出严格 JSON（不要代码块，不要解释）
- 每个热点给出 samples（至少 3 条样本，single 允许 1-2 条）
- 总数最多 {Local.TopK}

## 输出格式（严格 JSON）
{"hotspots": [{"hotspot_id": "H01", "title": "...", "summary": "...", "category": "trend|single", "overall_heat_score": 0, "coverage": {"source_count": 0, "companies": [], "platforms": []}, "should_chase": "yes|no", "chase_rationale": [], "samples": [{"platform": "...", "title": "...", "url": "...", "published_at": "...", "company": "...", "signal_level": "..."}]}]}
```

2. 将模型生成的聚类候选结果交给 `tech.cluster_or_fallback(raw_signals_json, clusters_json, top_k=6)` 做校验与兜底，得到最终热点聚类 JSON。
3. 用 `edit` 工具将最终热点聚类 JSON 写入 `Lab-01-Tech-Insights/output/clusters/hotspots.json`。
4. 在输出中区分 `cross_source_trends` 与 `high_signal_singles` 的主要发现。
5. 如果工具提示使用了兜底逻辑，在输出中注明。

## 阶段 3：生成热点洞察

1. 基于阶段 2 的热点聚类结果，按下面这段中文提示原文构造洞察请求；必须保留原文语义与结构，仅把占位符替换成实际 JSON：

```text
你是 Tech Insight Agent。任务：针对每个热点输出“发生了什么/为什么重要/影响谁/接下来怎么做”。

## 输入：热点聚类结果（严格 JSON）
{MessageText(Local.HotspotClusters)}

## 输出（严格 JSON）
{"insights": [{"hotspot_id": "H01", "title": "...", "what_changed": "...", "why_it_matters": "...", "who_is_impacted": [], "next_actions": [], "risk_notes": [], "references": []}]}
```

2. 将模型生成的洞察候选结果交给 `tech.insight_or_fallback(clusters_json, insights_json)` 做校验与兜底，得到最终洞察 JSON。
3. 用 `edit` 工具将最终洞察 JSON 写入 `Lab-01-Tech-Insights/output/insights/insights.json`。
4. 输出时覆盖“发生了什么 / 为什么重要 / 影响谁 / 接下来怎么做”四个维度。
5. 如果工具提示使用了兜底逻辑，在输出中注明。

## 阶段 4：生成并提交 Markdown 报告

1. 基于阶段 2 的聚类结果与阶段 3 的洞察结果，按下面这段中文提示原文构造报告请求；必须保留原文语义与结构，仅把占位符替换成实际 JSON：

```text
你是 Tech Report Writer。
请基于聚类与洞察生成一份 Markdown 报告（中英混合可接受，但以中文为主），结构包含：
- 24h 摘要
- Cross-source Trends（趋势）
- High-signal Singles（重要单条更新）
- Company Radar（公司雷达）
- DevTools Releases（工具链更新）
- Research Watch（研究趋势）

## 输入：聚类（JSON）
{MessageText(Local.HotspotClusters)}

## 输入：洞察（JSON）
{MessageText(Local.HotspotInsights)}

输出 Markdown，不要代码块。
```

2. 将模型生成的 Markdown 草稿交给 `tech.render_report_or_fallback(clusters_json, insights_json, draft_markdown)` 做校验与兜底，得到最终 Markdown。
3. 用 `edit` 工具将最终 Markdown 写入 `Lab-01-Tech-Insights/output/report.md`。
4. 再用 `edit` 工具将同一份 Markdown 写入 `Lab-01-Tech-Insights/frontend/report.md`，作为前端展示文件。
5. 通过 safe-outputs 的 `create-pull-request` 机制提交包含 `Lab-01-Tech-Insights/output/report.md` 和 `Lab-01-Tech-Insights/frontend/report.md` 的 PR。PR 标题应包含日期和报告摘要。不要引入额外的手工 git 流程。
6. 最终总结需说明报告输出路径、前端同步路径和 PR 编号。
7. 如果工具提示使用了兜底逻辑，在输出中注明。