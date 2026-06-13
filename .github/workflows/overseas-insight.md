---
name: Overseas Insight Workflow
on:
  workflow_dispatch:
  schedule:
    # 每天 UTC 21:00 = 北京时间次日 05:00（中国无夏令时，全年稳定）。
    # GitHub Actions 定时为尽力而为，可能延迟数分钟到数十分钟。
    - cron: "0 21 * * *"
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
      python3 -m pip install -r Lab-04-Overseas-Insights/mcp-scripts/requirements.txt
network:
  allowed:
    - defaults
    - python
    # 美妆护肤
    - "www.glossy.co"
    - "wwd.com"
    - "www.cosmeticsbusiness.com"
    - "www.premiumbeautynews.com"
    # 3C 电子
    - "www.theverge.com"
    - "www.engadget.com"
    - "www.gsmarena.com"
    - "www.androidauthority.com"
    - "www.notebookcheck.net"
    # 饰品配饰
    - "www.jckonline.com"
    - "www.professionaljeweller.com"
    - "www.nationaljeweler.com"
    - "rapaport.com"
    # 跨境电商 / 东南亚 / 榜单趋势贸易媒体
    - "www.techinasia.com"
    - "www.modernretail.co"
    - "www.retaildive.com"
    - "www.practicalecommerce.com"
    - "www.marketplacepulse.com"
    - "www.emarketer.com"
    # research-only 目标（尽力而为，常被反爬拦截）
    - "www.amazon.com"
    - "seller-us.tiktok.com"
    - "trends.google.com"
safe-outputs:
  create-pull-request:
    title-prefix: "[overseas-insight] "
    labels: [automation, overseas-insight]
mcp-scripts:
  overseas-read-source-list:
    description: "Read overseas source list configuration"
    inputs:
      source_list_path:
        type: string
        required: true
    run: |
      cd "$GITHUB_WORKSPACE"
      echo "{\"source_list_path\": \"$INPUT_SOURCE_LIST_PATH\"}" | python3 Lab-04-Overseas-Insights/mcp-scripts/overseas_read_source_list.py
  overseas-fetch-all-to-disk:
    description: "Fetch all baseline (RSS) sources to disk; research-only sources are skipped"
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
        default: 5
    timeout: 300
    run: |
      cd "$GITHUB_WORKSPACE"
      python3 -c "
      import json, sys
      sys.path.insert(0, 'Lab-04-Overseas-Insights/mcp-scripts')
      from overseas_insight_tools import overseas_fetch_all_to_disk
      result = overseas_fetch_all_to_disk(
          source_list_path='$INPUT_SOURCE_LIST_PATH',
          signals_dir='$INPUT_SIGNALS_DIR',
          timeout_seconds=int('${INPUT_TIMEOUT_SECONDS:-15}'),
          max_chars=int('${INPUT_MAX_CHARS:-200000}'),
          max_items_per_source=int('${INPUT_MAX_ITEMS_PER_SOURCE:-5}')
      )
      print(json.dumps(result, ensure_ascii=False, default=str))
      "
  overseas-load-articles-from-disk:
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
        default: 5
      time_window_hours:
        type: number
        default: 48
    run: |
      cd "$GITHUB_WORKSPACE"
      python3 -c "
      import json, sys
      sys.path.insert(0, 'Lab-04-Overseas-Insights/mcp-scripts')
      from overseas_insight_tools import overseas_load_articles_from_disk
      result = overseas_load_articles_from_disk(
          signals_dir='$INPUT_SIGNALS_DIR',
          source_list_path='$INPUT_SOURCE_LIST_PATH',
          max_items_per_source=int('${INPUT_MAX_ITEMS_PER_SOURCE:-5}'),
          time_window_hours=int('${INPUT_TIME_WINDOW_HOURS:-48}')
      )
      print(json.dumps(result, ensure_ascii=False, default=str))
      "
  overseas-cluster-or-fallback:
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
        default: 9
    run: |
      cd "$GITHUB_WORKSPACE"
      python3 -c "import os, json, sys, subprocess; payload = json.dumps({'raw_signals_json': os.environ.get('INPUT_RAW_SIGNALS_JSON', ''), 'clusters_json': os.environ.get('INPUT_CLUSTERS_JSON', ''), 'top_k': int(os.environ.get('INPUT_TOP_K') or 9)}); sys.exit(subprocess.run([sys.executable, 'Lab-04-Overseas-Insights/mcp-scripts/overseas_cluster_or_fallback.py'], input=payload, text=True).returncode)"
  overseas-insight-or-fallback:
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
      python3 -c "import os, json, sys, subprocess; payload = json.dumps({'clusters_json': os.environ.get('INPUT_CLUSTERS_JSON', ''), 'insights_json': os.environ.get('INPUT_INSIGHTS_JSON', '')}); sys.exit(subprocess.run([sys.executable, 'Lab-04-Overseas-Insights/mcp-scripts/overseas_insight_or_fallback.py'], input=payload, text=True).returncode)"
  overseas-render-report-or-fallback:
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
      python3 -c "import os, json, sys, subprocess; payload = json.dumps({'clusters_json': os.environ.get('INPUT_CLUSTERS_JSON', ''), 'insights_json': os.environ.get('INPUT_INSIGHTS_JSON', ''), 'draft_markdown': os.environ.get('INPUT_DRAFT_MARKDOWN', '')}); sys.exit(subprocess.run([sys.executable, 'Lab-04-Overseas-Insights/mcp-scripts/overseas_render_report_or_fallback.py'], input=payload, text=True).returncode)"
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
      python3 -c "import os, json, sys, subprocess; payload = json.dumps({'path': os.environ.get('INPUT_PATH', ''), 'text': os.environ.get('INPUT_TEXT', ''), 'overwrite': os.environ.get('INPUT_OVERWRITE', 'true').strip().lower() not in ('false', '0', 'no')}); sys.exit(subprocess.run([sys.executable, 'Lab-04-Overseas-Insights/mcp-scripts/write_text_file.py'], input=payload, text=True).returncode)"
---

# Overseas Insight 工作流（出海市场洞察）

目标：每天生成一份**跨境电商出海市场调查报告**，聚焦三大品类——**美妆护肤 / 3C电子 / 饰品配饰**，覆盖
**北美 / 欧洲 / 东南亚 / 全球** 市场，产出热点话题、热门产品/潜力爆品与可执行的选品与营销洞察。

数据策略：**RSS 基线为主 + 有限深度研究增强**。RSS 种子源提供可靠且低成本的基线信号；在此基础上，在网络白名单内进行
**严格受限**的联网研究，补充少量高价值「热产品/爆品」证据。⚠️ 运行环境对累计「毛 token」有 **25M 硬上限**（不可调），
若深度研究不受限会在进入聚类前耗尽预算、导致整轮失败 —— 因此必须严格遵守下方 token 预算约束。

默认配置如下：

- `source_list_path`: `Lab-04-Overseas-Insights/input/api/source_list.json`
- `signals_dir`: `Lab-04-Overseas-Insights/output/signals`
- `output_dir`: `Lab-04-Overseas-Insights/output`
- `time_window_hours`: `48`
- `top_k`: `9`（约每品类 3 个）
- `max_items_per_source`: `5`
- `timeout_seconds`: `15`
- `max_chars`: `200000`

执行约束：

- 全程只使用仓库根目录相对路径，不要写绝对路径。
- 所有面向模型的提示词必须使用中文。报告正文以中文为主。
- 关键中间产物必须落盘：`raw_signals.json`、`clusters/hotspots.json`、`insights/insights.json`、`report.md`。
- 最终除写入 `Lab-04-Overseas-Insights/output/report.md` 外，还要把同一份 Markdown 写入
  `Lab-04-Overseas-Insights/frontend/report.md`，并通过 safe-outputs 的提交机制提交该前端文件。
- **联网研究只能访问 frontmatter `network.allowed` 白名单内的域名**；遇到被拦截/不可达的目标（如 Amazon、TikTok、Google Trends
  常被反爬），不要反复重试，应记录该缺口并以 RSS 基线兜底继续。
- **token 预算（硬约束）**：运行环境累计「毛 token」上限 **25M**，超出即整轮失败、无报告产出。为此：
  (a) 阶段 1.5 的联网研究 **最多抓取 6 个页面、单轮完成**；
  (b) 每次抓取必须先用 shell 把页面**提取为纯文本并截断到约 1500 字符**再阅读，**严禁把整页 HTML/原始响应读入模型上下文**；
  (c) 不要多轮反复抓取同类页面，不要对失败目标重试；
  (d) 尽快进入阶段 2-4（聚类/洞察/报告），各阶段 LLM 调用务必简洁，避免重复粘贴大段原文。
- 不要引入额外的手工 git 流程；提交统一走 safe-outputs。

## 阶段 0：深度研究规划

1. 调用 `overseas.read_source_list(source_list_path)` 读取种子源，按 `category`（beauty/3c/jewelry）× `markets`（na/eu/sea/global）分组。
2. 规划 **至多 6 个**最高价值的定向抓取目标（覆盖三品类的热点/爆品即可），例如「美妆 北美 爆品」「3C gadget trending Europe」
   「饰品 跨境 热销」。只选信息密度最高的少量目标，**不要逐一枚举所有品类×市场组合**。
3. 标记 `fetchable: research-only` 的源（Amazon/TikTok/Google Trends）为「尽力而为」目标，不可达时直接跳过，不重试。

## 阶段 1：基线抓取并装载原始信号

1. 调用 `overseas.fetch_all_to_disk(source_list_path, signals_dir, timeout_seconds=15, max_chars=200000, max_items_per_source=5)`
   抓取所有 RSS 基线源并落盘到 `signals_dir`（research-only 源会被自动跳过）。
2. 调用 `overseas.load_articles_from_disk(signals_dir, source_list_path, max_items_per_source=5, time_window_hours=48)` 生成原始信号 JSON。
3. 用 `edit` 工具将原始信号 JSON 写入 `Lab-04-Overseas-Insights/output/raw_signals.json`。
4. 简要汇报源数量、抓取成功数、纳入时间窗与原始信号保存位置。如使用了兜底逻辑请注明。

## 阶段 1.5：深度联网研究与信号增强

1. **单轮、至多 6 次抓取**。对每个目标必须先用 shell 提取纯文本摘要再阅读，例如：
   `curl -sL --max-time 15 "<url>" | python3 -c "import sys,re; t=re.sub(r'<[^>]+>',' ',sys.stdin.read()); print(re.sub(r'\s+',' ',t)[:1500])"`
   **只把这 ≤1500 字符的摘要纳入推理**，严禁读入整页 HTML 或原始响应。
2. 从摘要中提炼「热门产品 / 潜力爆品」要点：品类、目标市场、价格带、核心卖点、为什么火（尽量带可引用链接）。
3. 将提炼出的少量高价值信号并入工作信号集，与 `raw_signals.json` 一并进入聚类。
4. 任一目标不可达或为 research-only 时，**直接跳过、不重试**，并在报告「数据来源」注明缺口，以 RSS 基线继续。
5. 完成本阶段后**立即进入阶段 2**，不要继续扩大抓取范围或反复抓取。

## 阶段 2：聚类热点（分品类 / 分市场）

1. 基于阶段 1 / 1.5 的信号，按下面这段中文提示原文构造聚类请求；保留原文语义与结构，仅把占位符替换成实际值与实际 JSON：

```text
你是 Overseas Market Clustering Agent。
任务：把过去 {Local.TimeWindowHours} 小时内、关于跨境电商出海（美妆护肤/3C/饰品）的信号聚合成可行动的热点主题/重要更新。

## 输入（严格 JSON）
{MessageText(Local.RawSignals)}

## 聚类原则（混合）
- 先按结构化标签分桶：category(beauty|3c|jewelry) / markets(na|eu|sea|global) / signal_level / 品牌
- 再在桶内按主题合并（标题 + 摘要 + 链接域名 + 产品/品牌）
- 同时保留两类输出：
  1) 跨源趋势：多来源共振的趋势主题（coverage 高）
  2) 高信号单条：单来源但信号强（S/A 或榜单/爆品/官方更新）的重要更新

## 强约束
- 必须输出严格 JSON（不要代码块，不要解释）
- 每个热点必须带 categories（beauty|3c|jewelry 子集）与 markets（na|eu|sea|global 子集）
- 每个热点给出 samples（至少 3 条，single 允许 1-2 条）
- 总数最多 {Local.TopK}

## 输出格式（严格 JSON）
{"hotspots": [{"hotspot_id": "H01", "title": "...", "summary": "...", "category": "trend|single", "categories": ["beauty"], "markets": ["na"], "overall_heat_score": 0, "coverage": {"source_count": 0, "companies": [], "platforms": []}, "should_chase": "yes|no", "chase_rationale": [], "samples": [{"platform": "...", "title": "...", "url": "...", "published_at": "...", "company": "...", "signal_level": "..."}]}]}
```

2. 将模型生成的聚类候选结果交给 `overseas.cluster_or_fallback(raw_signals_json, clusters_json, top_k=9)` 做校验与兜底，得到最终热点聚类 JSON。
3. 用 `edit` 工具将最终热点聚类 JSON 写入 `Lab-04-Overseas-Insights/output/clusters/hotspots.json`。
4. 输出时区分「跨源趋势」与「高信号单条」的主要发现。如使用了兜底逻辑请注明。

## 阶段 3：生成热点洞察

1. 基于阶段 2 的聚类结果，按下面这段中文提示原文构造洞察请求；保留原文语义与结构，仅替换占位符为实际 JSON：

```text
你是 Overseas Market Insight Agent。任务：针对每个热点输出"发生了什么 / 为什么重要 / 影响谁 / 接下来怎么做"。
若为热门产品/爆品，补充 price_band（价格带）、selling_points（核心卖点）、target_market（目标市场）。

## 输入：热点聚类结果（严格 JSON）
{MessageText(Local.HotspotClusters)}

## 输出（严格 JSON）
{"insights": [{"hotspot_id": "H01", "title": "...", "what_changed": "...", "why_it_matters": "...", "who_is_impacted": [], "next_actions": [], "price_band": "...", "selling_points": [], "target_market": [], "risk_notes": [], "references": []}]}
```

2. 将模型生成的洞察候选结果交给 `overseas.insight_or_fallback(clusters_json, insights_json)` 做校验与兜底，得到最终洞察 JSON。
3. 用 `edit` 工具将最终洞察 JSON 写入 `Lab-04-Overseas-Insights/output/insights/insights.json`。
4. 输出覆盖四个维度（发生了什么 / 为什么重要 / 影响谁 / 接下来怎么做）。如使用了兜底逻辑请注明。

## 阶段 4：生成并提交 Markdown 报告

1. 基于阶段 2 聚类与阶段 3 洞察，按下面这段中文提示原文构造报告请求；保留原文语义与结构，仅替换占位符为实际 JSON：

```text
你是 Overseas Market Report Writer。
请基于聚类与洞察生成一份中文 Markdown 出海市场洞察日报，结构包含：
- 今日摘要（3-5 条跨品类 TL;DR）
- 热点话题（分品类：美妆护肤 / 3C电子 / 饰品配饰）
- 热门产品 / 潜力爆品（分品类表格：主题/产品 | 市场 | 价格带 | 核心卖点 | 来源）
- 分市场速览（北美 / 欧洲 / 东南亚 / 全球，各 3-5 条要点）
- 选品与营销行动建议（选品方向 / 内容营销角度 / 投放建议）
- 风险与合规提示（关税 / 认证 / 平台政策 / 侵权 / 物流）
- 数据来源（引用链接，并标注 RSS基线 vs 深度研究；注明被拦截/不可达的缺口）

## 输入：聚类（JSON）
{MessageText(Local.HotspotClusters)}

## 输入：洞察（JSON）
{MessageText(Local.HotspotInsights)}

输出 Markdown，不要代码块。
```

2. 将模型生成的 Markdown 草稿交给 `overseas.render_report_or_fallback(clusters_json, insights_json, draft_markdown)` 做校验与兜底，得到最终 Markdown。
3. 用 `edit` 工具将最终 Markdown 写入 `Lab-04-Overseas-Insights/output/report.md`。
4. 再用 `edit` 工具将同一份 Markdown 写入 `Lab-04-Overseas-Insights/frontend/report.md`，作为前端展示文件。
5. 通过 safe-outputs 的 `create-pull-request` 机制提交包含 `Lab-04-Overseas-Insights/output/report.md` 和
   `Lab-04-Overseas-Insights/frontend/report.md` 的 PR。PR 标题应包含日期和报告摘要。
6. 最终总结需说明报告输出路径、前端同步路径和 PR 编号。如使用了兜底逻辑请注明。
