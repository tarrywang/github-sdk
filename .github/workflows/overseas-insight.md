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
  - name: Fetch e-commerce bestsellers via ScraperAPI (pre-step, key isolated from agent)
    env:
      SCRAPER_API_KEY: ${{ secrets.SCRAPER_API_KEY }}
    run: |
      # Best-effort: renders the 5 bestseller pages via proxy and writes compact
      # extracts to output/signals/bestsellers/ for the agent to read. The API key
      # stays in this step only — it never enters the agent/LLM sandbox. Never fails
      # the build on scrape gaps (no key / blocked sites are recorded as gaps).
      python3 Lab-04-Overseas-Insights/mcp-scripts/overseas_fetch_bestsellers.py || true
network:
  allowed:
    - defaults
    - python
    # 美妆护肤（北美）基线源
    - "www.glossy.co"
    - "wwd.com"
    - "www.modernretail.co"
    - "www.beautyindependent.com"
    # 北美热销榜 research-only 目标（尽力而为，多为 SPA/反爬，常被拦截）
    - "www.amazon.com"
    - "www.sephora.com"
    - "www.ulta.com"
    - "www.target.com"
    - "shop.tiktok.com"
    - "www.tiktok.com"
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
    description: "校验+兜底聚类结果。强烈建议用文件路径参数（raw_signals_path / clusters_candidate_path / out_path），避免把大 JSON 作为字符串参数传入（网关对单参数有 10KB 上限）。工具会把最终热点写入 out_path。"
    inputs:
      raw_signals_path:
        type: string
        required: false
      clusters_candidate_path:
        type: string
        required: false
      out_path:
        type: string
        required: false
      raw_signals_json:
        type: string
        required: false
      clusters_json:
        type: string
        required: false
      top_k:
        type: number
        default: 9
    run: |
      cd "$GITHUB_WORKSPACE"
      python3 -c "import os, json, sys, subprocess; payload = json.dumps({'raw_signals_json': os.environ.get('INPUT_RAW_SIGNALS_JSON', ''), 'clusters_json': os.environ.get('INPUT_CLUSTERS_JSON', ''), 'top_k': int(os.environ.get('INPUT_TOP_K') or 9), 'raw_signals_path': os.environ.get('INPUT_RAW_SIGNALS_PATH', ''), 'clusters_candidate_path': os.environ.get('INPUT_CLUSTERS_CANDIDATE_PATH', ''), 'out_path': os.environ.get('INPUT_OUT_PATH', '')}); sys.exit(subprocess.run([sys.executable, 'Lab-04-Overseas-Insights/mcp-scripts/overseas_cluster_or_fallback.py'], input=payload, text=True).returncode)"
  overseas-insight-or-fallback:
    description: "校验+兜底洞察结果。强烈建议用文件路径参数（clusters_path / insights_candidate_path / out_path），避免把大 JSON 作为字符串参数传入（单参数 10KB 上限）。工具会把最终洞察写入 out_path。"
    inputs:
      clusters_path:
        type: string
        required: false
      insights_candidate_path:
        type: string
        required: false
      out_path:
        type: string
        required: false
      clusters_json:
        type: string
        required: false
      insights_json:
        type: string
        required: false
    run: |
      cd "$GITHUB_WORKSPACE"
      python3 -c "import os, json, sys, subprocess; payload = json.dumps({'clusters_json': os.environ.get('INPUT_CLUSTERS_JSON', ''), 'insights_json': os.environ.get('INPUT_INSIGHTS_JSON', ''), 'clusters_path': os.environ.get('INPUT_CLUSTERS_PATH', ''), 'insights_candidate_path': os.environ.get('INPUT_INSIGHTS_CANDIDATE_PATH', ''), 'out_path': os.environ.get('INPUT_OUT_PATH', '')}); sys.exit(subprocess.run([sys.executable, 'Lab-04-Overseas-Insights/mcp-scripts/overseas_insight_or_fallback.py'], input=payload, text=True).returncode)"
  overseas-products-or-fallback:
    description: "校验+兜底「北美热销 TOP5 产品」清单（排名/评分/评价数/趋势为销量代理，无精确件数/GMV）。用路径参数 products_candidate_path / out_path；工具会把最终 TOP5 写入 out_path，候选不可用时回退为空清单并附缺口说明（绝不编造销量）。"
    inputs:
      products_candidate_path:
        type: string
        required: false
      out_path:
        type: string
        required: false
      top_n:
        type: number
        default: 5
      products_json:
        type: string
        required: false
    run: |
      cd "$GITHUB_WORKSPACE"
      python3 -c "import os, json, sys, subprocess; payload = json.dumps({'products_json': os.environ.get('INPUT_PRODUCTS_JSON', ''), 'products_candidate_path': os.environ.get('INPUT_PRODUCTS_CANDIDATE_PATH', ''), 'out_path': os.environ.get('INPUT_OUT_PATH', ''), 'top_n': int(os.environ.get('INPUT_TOP_N') or 5)}); sys.exit(subprocess.run([sys.executable, 'Lab-04-Overseas-Insights/mcp-scripts/overseas_products_or_fallback.py'], input=payload, text=True).returncode)"
  overseas-render-report-or-fallback:
    description: "校验+兜底报告渲染。强烈建议用文件路径参数（clusters_path / insights_path / products_path / draft_path / out_path / frontend_out_path）。工具会把最终 Markdown 同时写入 out_path 与 frontend_out_path，返回精简状态（无需再用 edit 写文件）。"
    inputs:
      clusters_path:
        type: string
        required: false
      insights_path:
        type: string
        required: false
      products_path:
        type: string
        required: false
      draft_path:
        type: string
        required: false
      out_path:
        type: string
        required: false
      frontend_out_path:
        type: string
        required: false
      clusters_json:
        type: string
        required: false
      insights_json:
        type: string
        required: false
      draft_markdown:
        type: string
        required: false
    run: |
      cd "$GITHUB_WORKSPACE"
      python3 -c "import os, json, sys, subprocess; payload = json.dumps({'clusters_json': os.environ.get('INPUT_CLUSTERS_JSON', ''), 'insights_json': os.environ.get('INPUT_INSIGHTS_JSON', ''), 'draft_markdown': os.environ.get('INPUT_DRAFT_MARKDOWN', ''), 'clusters_path': os.environ.get('INPUT_CLUSTERS_PATH', ''), 'insights_path': os.environ.get('INPUT_INSIGHTS_PATH', ''), 'products_path': os.environ.get('INPUT_PRODUCTS_PATH', ''), 'draft_path': os.environ.get('INPUT_DRAFT_PATH', ''), 'out_path': os.environ.get('INPUT_OUT_PATH', ''), 'frontend_out_path': os.environ.get('INPUT_FRONTEND_OUT_PATH', '')}); sys.exit(subprocess.run([sys.executable, 'Lab-04-Overseas-Insights/mcp-scripts/overseas_render_report_or_fallback.py'], input=payload, text=True).returncode)"
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

目标：每天生成一份**跨境电商出海市场调查报告**，**当前阶段仅聚焦单一品类「美妆护肤」、单一市场「北美」**，产出两部分：
（A）该品类在北美市场的**热点话题**与可执行的选品与营销洞察；
（B）**北美热销 TOP5 产品**——基于主流电商榜单的「销量代理」指标（排名 / 评分 / 评价数 / 趋势）与可引用链接。
（3C、饰品及其他市场暂不纳入，待本工作流稳定后再扩展。）

数据策略：**RSS 基线为主 + 有限深度研究增强 + 北美电商榜单研究**。RSS 种子源提供可靠且低成本的基线信号；在网络白名单内进行
**严格受限**的联网研究，补充少量高价值「美妆北美热产品/爆品」证据，并抓取 5 大电商（Amazon / Sephora / Ulta / Target / TikTok Shop）
的畅销榜以提炼 TOP5 产品。⚠️ **关于销量数据的诚实口径**：免费抓取**拿不到精确销量（件数/GMV）**——这类数据只有付费工具（Jungle Scout /
Helium 10 / Similarweb 等）才有；且这些电商站点多为 SPA/强反爬，常只返回部分文本。因此 TOP5 一律以**公开榜单排名 + 评分 + 评价数 +
排名变化/「trending」标记**作为销量代理，**严禁编造任何销量数字**；抓不到的站点直接标注缺口，并用 RSS 新闻里出现的热门品牌/产品兜底补全。

数据策略仍受 **25M「有效 token」硬上限**约束（不可调），必须严格遵守下方 token 预算约束并保持范围聚焦（仅美妆·北美）。

默认配置如下：

- `source_list_path`: `Lab-04-Overseas-Insights/input/api/source_list.json`
- `signals_dir`: `Lab-04-Overseas-Insights/output/signals`
- `output_dir`: `Lab-04-Overseas-Insights/output`
- `time_window_hours`: `72`（美妆资讯更新较慢，窗口放宽以确保有内容）
- `top_k`: `6`（热点数，仅美妆·北美）
- `top_n_products`: `5`（北美热销产品数）
- `bestseller_targets`: source_list 中 `fetchable=research-only` 且 `research_kind=bestseller` 的 5 个站点（Amazon / Sephora / Ulta / Target / TikTok Shop）
- `max_items_per_source`: `5`
- `timeout_seconds`: `15`
- `max_chars`: `200000`

执行约束：

- 全程只使用仓库根目录相对路径，不要写绝对路径。
- 所有面向模型的提示词必须使用中文。报告正文以中文为主。
- 关键中间产物必须落盘：`raw_signals.json`、`clusters/hotspots.json`、`insights/insights.json`、`products/top_products.json`、`report.md`。
- 最终除写入 `Lab-04-Overseas-Insights/output/report.md` 外，还要把同一份 Markdown 写入
  `Lab-04-Overseas-Insights/frontend/report.md`，并通过 safe-outputs 的提交机制提交该前端文件。
- **联网研究只能访问 frontmatter `network.allowed` 白名单内的域名**；遇到被拦截/不可达的目标（如 Amazon、TikTok、Google Trends
  常被反爬），不要反复重试，应记录该缺口并以 RSS 基线兜底继续。
- **token 预算（硬约束）**：运行环境对累计 token 有 **25M「有效 token」上限**（=实际 token × 模型倍率，约 10×，不可调），超出即整轮失败、无报告产出。
  关键事实：上限不是被数据量撑爆的，而是被**回合数 × 每回合重发的上下文**撑爆的——回合越多、上下文越大，重发成本越高。**控制回合数是第一要务。** 为此：
  (a) 阶段 1.5 的新闻深度研究 **最多抓取 4 个页面、单轮完成**；电商榜单由**前置步骤**统一抓取并落盘，agent 在阶段 1.6**只读已落盘的提取文件、不自行联网抓电商站**；
  (b) 每次新闻抓取必须先用 shell 把页面**提取为纯文本并截断到约 1500 字符**再阅读，**严禁把整页 HTML/原始响应读入模型上下文**；读取电商提取文件时也只取必要片段；
  (c) 不要多轮反复抓取同类页面，不要对失败/被拦截的目标重试；
  (d) 尽快进入阶段 2-4（聚类/洞察/产品/报告），各阶段 LLM 调用务必简洁，避免重复粘贴大段原文。
- **🚨 MCP 工具调用必须用「文件路径」而非「内联 JSON 内容」（这是上一轮失败的根因）**：
  - 网关对**单个字符串参数有 10KB 硬上限**。把 `raw_signals.json`（约 23KB）、`insights.json`（约 13KB）等整段 JSON 作为字符串参数传入会被拒绝，并触发反复裁剪/转义/重试，**额外消耗大量回合与上下文，直接撑爆 25M**。
  - 因此调用 `overseas.cluster_or_fallback` / `overseas.insight_or_fallback` / `overseas.products_or_fallback` / `overseas.render_report_or_fallback` 时，**一律传文件路径参数**（`raw_signals_path` / `clusters_candidate_path` / `clusters_path` / `insights_candidate_path` / `insights_path` / `products_candidate_path` / `products_path` / `draft_path` / `out_path` / `frontend_out_path`），**绝不传 `*_json` / `draft_markdown` 等内联内容参数**。
  - 工具会自行从路径读取输入、把最终结果**直接写入 `out_path`**（报告还会同时写 `frontend_out_path`），并只返回精简状态（mode/计数/路径）。**因此无需再用 `edit` 重复写这些产物文件。**
- **🚨 候选 JSON 必须用 Python `json.dump` 写文件，不要手写 heredoc**：各阶段的 LLM 候选结果（聚类/洞察）请在 shell 里构造成 Python dict 后用
  `json.dump(obj, open(path,'w'), ensure_ascii=False)` 落盘，**严禁用 heredoc 手敲 JSON**（中文引号「」与未转义的 `"` 会反复打断解析、白白浪费回合）。
- **不要把大文件 `cat` 进上下文**：需要查看产物时只 `tail`/读必要片段；中间产物之间通过**磁盘文件路径**衔接，不要在回合间反复粘贴大段 JSON/Markdown。
- 不要引入额外的手工 git 流程；提交统一走 safe-outputs。

## 阶段 0：深度研究规划

1. 调用 `overseas.read_source_list(source_list_path)` 读取种子源（均为 `category=beauty` / `markets=[na]`）。
2. 规划新闻深度研究：**至多 4 个**最高价值的定向抓取目标，**仅围绕「美妆护肤 × 北美」的热点/爆品**，例如「skincare bestseller US」。只选信息密度最高的少量目标。
3. 电商榜单（Amazon / Sephora / Ulta / Target / TikTok Shop）由工作流**前置步骤经 ScraperAPI 代理**抓取并落盘到
   `output/signals/bestsellers/`，agent 无需自行抓取；这些站多为 SPA/强反爬，部分（如 Target/TikTok，或免费套餐下的受保护域名）可能被拦——
   **作为「尽力而为」目标**，被拦的站在阶段 1.6 据实记缺口、用新闻信号兜底。

## 阶段 1：基线抓取并装载原始信号

1. 调用 `overseas.fetch_all_to_disk(source_list_path, signals_dir, timeout_seconds=15, max_chars=200000, max_items_per_source=5)`
   抓取所有 RSS 基线源并落盘到 `signals_dir`（research-only 源会被自动跳过）。
2. 调用 `overseas.load_articles_from_disk(signals_dir, source_list_path, max_items_per_source=5, time_window_hours=72)` 生成原始信号 JSON。
3. 用 `edit` 工具将原始信号 JSON 写入 `Lab-04-Overseas-Insights/output/raw_signals.json`。
4. 简要汇报源数量、抓取成功数、纳入时间窗与原始信号保存位置。如使用了兜底逻辑请注明。

## 阶段 1.5：深度联网研究与信号增强

1. **单轮、至多 4 次抓取**，仅围绕「美妆护肤 × 北美」。对每个目标必须先用 shell 提取纯文本摘要再阅读，例如：
   `curl -sL --max-time 15 "<url>" | python3 -c "import sys,re; t=re.sub(r'<[^>]+>',' ',sys.stdin.read()); print(re.sub(r'\s+',' ',t)[:1500])"`
   **只把这 ≤1500 字符的摘要纳入推理**，严禁读入整页 HTML 或原始响应。
2. 从摘要中提炼「美妆护肤热门产品 / 潜力爆品（北美）」要点：子类（护肤/彩妆/香水等）、价格带、核心卖点、为什么火（尽量带可引用链接）。
3. 把提炼出的少量高价值信号（research-enhanced）用 Python 读出 `Lab-04-Overseas-Insights/output/raw_signals.json`、
   追加到其 `items` 列表后再 `json.dump(..., ensure_ascii=False)` 写回**同一文件**，使其与 RSS 基线信号一并进入聚类（后续聚类工具按路径读取该文件）。
4. 任一目标不可达或为 research-only 时，**直接跳过、不重试**，并在报告「数据来源」注明缺口，以 RSS 基线继续。
5. 完成本阶段后**进入阶段 1.6**，不要继续扩大抓取范围或反复抓取。

## 阶段 1.6：北美电商畅销榜研究（热销 TOP5 产品）

> ⚠️ 诚实口径：免费抓取**拿不到精确销量（件数/GMV）**；以**公开榜单排名 + 评分 + 评价数 + 趋势**作为销量代理，**严禁编造销量数字**。
> 榜单页已由工作流的**前置步骤**（ScraperAPI 代理，密钥仅存在于该步骤、不进入本沙箱）抓取并落盘到 `Lab-04-Overseas-Insights/output/signals/bestsellers/`。
> 本阶段**不要自己联网抓电商站**，只读取这些已落盘的精简提取文件。

1. 读取 `Lab-04-Overseas-Insights/output/signals/bestsellers/_summary.json` 了解各站抓取状态（ok / 被拦 / 缺口），再读取存在的 `<platform>.txt`
   提取文件（如 `amazon-bestsellers-beauty.txt`）。这些文件含 `NAME_CANDIDATES / RATINGS / PRICES / TEXT_WINDOW`，其中 **Amazon 的 TEXT_WINDOW
   通常带有完整的 `#排名 产品名 X.X out of 5 stars 评价数 $价格` 有序列表**，可直接解析出真实排名/评分/评价数/价格。
2. 以这些**真实榜单数据为主**提炼北美美妆热销 TOP5；某站被拦/无数据时，用阶段 1/1.5 的 RSS 新闻里反复出现的热门品牌/产品兜底补全，并在 `evidence` 里据实标注。
   每个产品给出：`rank`、`name`、`brand`、`subcategory`（护肤/彩妆/香水/个护）、`price`（价格带）、`rating`（评分，无则留空）、
   `review_count`（评价数，无则留空）、`trend`（上升/稳定/下滑/新晋/长期在榜）、`platform`（Amazon/Sephora/Ulta/Target/TikTok Shop）、
   `url`（可引用链接）、`evidence`（数据来源：**榜单页**还是**新闻信号兜底**）、`selling_points`（核心卖点）、`why_hot`（为什么火）。
3. 把 TOP5 候选**用 Python `json.dump(obj, open('/tmp/gh-aw/agent/products_candidate.json','w'), ensure_ascii=False)` 落盘**（严禁 heredoc 手写 JSON）。目标结构：
   `{"products": [{"rank":1, "name":"...", "brand":"...", "subcategory":"...", "price":"...", "rating":4.8, "review_count":82000, "trend":"...", "platform":"...", "url":"...", "evidence":"...", "selling_points":[], "why_hot":"..."}]}`
4. 调用 `overseas.products_or_fallback`，**只传文件路径参数**：
   - `products_candidate_path="/tmp/gh-aw/agent/products_candidate.json"`
   - `top_n=5`
   - `out_path="Lab-04-Overseas-Insights/output/products/top_products.json"`
   工具会校验/兜底后把最终 TOP5 写入 `out_path` 并返回精简状态。**不要再用 `edit` 写该文件。**
5. 简要汇报各站抓取状态与 TOP5 概览，并注明哪些指标来自**电商榜单**、哪些来自**新闻兜底**。完成后进入阶段 2。

## 阶段 2：聚类热点（美妆护肤 · 北美）

1. 以你**已读取的** `Lab-04-Overseas-Insights/output/raw_signals.json` 内容为输入（**无需再把整段 JSON 粘贴进上下文**），按下面这段中文提示的语义与结构进行聚类推理：

```text
你是 Overseas Market Clustering Agent。
任务：把过去 72 小时内、关于「美妆护肤」品类在「北美」市场出海的信号聚合成可行动的热点主题/重要更新。

## 输入
已落盘的 raw_signals.json（其 items 即待聚类信号）。

## 聚类原则（混合）
- 先按结构化标签分桶：美妆子类（护肤/彩妆/香水/个护等）/ signal_level / 品牌
- 再在桶内按主题合并（标题 + 摘要 + 链接域名 + 产品/品牌）
- 同时保留两类输出：
  1) 跨源趋势：多来源共振的趋势主题（coverage 高）
  2) 高信号单条：单来源但信号强（S/A 或榜单/爆品/官方更新）的重要更新

## 强约束
- 每个热点固定 categories=["beauty"]、markets=["na"]
- 每个热点给出 samples（至少 3 条，single 允许 1-2 条）
- 总数最多 6

## 目标结构（写入候选文件时遵循）
{"hotspots": [{"hotspot_id": "H01", "title": "...", "summary": "...", "category": "trend|single", "categories": ["beauty"], "markets": ["na"], "overall_heat_score": 0, "coverage": {"source_count": 0, "companies": [], "platforms": []}, "should_chase": "yes|no", "chase_rationale": [], "samples": [{"platform": "...", "title": "...", "url": "...", "published_at": "...", "company": "...", "signal_level": "..."}]}]}
```

2. 把聚类候选**用 Python `json.dump(obj, open('/tmp/gh-aw/agent/clusters_candidate.json','w'), ensure_ascii=False)` 落盘**（严禁 heredoc 手写 JSON）。
3. 调用 `overseas.cluster_or_fallback`，**只传文件路径参数**（绝不传内联 JSON）：
   - `raw_signals_path="Lab-04-Overseas-Insights/output/raw_signals.json"`
   - `clusters_candidate_path="/tmp/gh-aw/agent/clusters_candidate.json"`
   - `top_k=6`
   - `out_path="Lab-04-Overseas-Insights/output/clusters/hotspots.json"`
   工具会校验/兜底后把最终热点写入 `out_path` 并返回精简状态（mode/热点数/路径）。**不要再用 `edit` 写 hotspots.json。**
4. 输出时区分「跨源趋势」与「高信号单条」的主要发现。如使用了兜底逻辑请注明。

## 阶段 3：生成热点洞察

1. 以阶段 2 的聚类结果（你已从 `cluster_or_fallback` 的返回状态得知，必要时读取 `Lab-04-Overseas-Insights/output/clusters/hotspots.json`）为输入，按下面这段中文提示的语义与结构生成洞察：

```text
你是 Overseas Market Insight Agent。任务：针对每个热点输出"发生了什么 / 为什么重要 / 影响谁 / 接下来怎么做"。
若为热门产品/爆品，补充 price_band（价格带）、selling_points（核心卖点）、target_market（目标市场）。

## 输入：热点聚类结果
已落盘的 clusters/hotspots.json。

## 目标结构（写入候选文件时遵循）
{"insights": [{"hotspot_id": "H01", "title": "...", "what_changed": "...", "why_it_matters": "...", "who_is_impacted": [], "next_actions": [], "price_band": "...", "selling_points": [], "target_market": [], "risk_notes": [], "references": []}]}
```

2. 把洞察候选**用 Python `json.dump(obj, open('/tmp/gh-aw/agent/insights_candidate.json','w'), ensure_ascii=False)` 落盘**（严禁 heredoc 手写 JSON）。
3. 调用 `overseas.insight_or_fallback`，**只传文件路径参数**：
   - `clusters_path="Lab-04-Overseas-Insights/output/clusters/hotspots.json"`
   - `insights_candidate_path="/tmp/gh-aw/agent/insights_candidate.json"`
   - `out_path="Lab-04-Overseas-Insights/output/insights/insights.json"`
   工具会校验/兜底后把最终洞察写入 `out_path` 并返回精简状态。**不要再用 `edit` 写 insights.json。**
4. 输出覆盖四个维度（发生了什么 / 为什么重要 / 影响谁 / 接下来怎么做）。如使用了兜底逻辑请注明。

## 阶段 4：生成并提交 Markdown 报告

1. 以阶段 2 聚类与阶段 3 洞察为输入（必要时读取 `clusters/hotspots.json` 与 `insights/insights.json`），按下面这段中文提示的语义与结构撰写报告：

```text
你是 Overseas Market Report Writer。
请基于聚类、洞察与北美热销 TOP5 产品生成一份中文 Markdown 报告，主题固定为「美妆护肤 · 北美市场 出海洞察日报」，结构包含：
- 今日摘要（3-5 条 TL;DR）
- 热点话题（美妆护肤 · 北美）
- 北美热销 TOP5 产品（表格：排名 | 产品 | 品牌 | 子类 | 价格带 | 评分 | 评价数 | 趋势 | 平台；并逐条给「为什么火/核心卖点」+可引用链接）
  ⚠️ 明确写出口径说明：排名/评分/评价数/趋势为**销量代理指标**，非精确销量；注明哪些来自电商榜单、哪些来自新闻兜底、哪些站点被拦缺数据。
- 选品与营销行动建议（选品方向 / 内容营销角度 / 投放建议，针对北美美妆）
- 风险与合规提示（美妆重点：FDA / MoCRA 注册与备案、成分与标签合规、平台类目政策、知识产权）
- 数据来源（引用链接，并标注 RSS基线 vs 深度研究 vs 电商榜单；注明被拦截/不可达的缺口）

## 输入
已落盘的 clusters/hotspots.json、insights/insights.json 与 products/top_products.json。

输出 Markdown，不要代码块。
```

2. 把生成的 Markdown 草稿**写入文件** `/tmp/gh-aw/agent/report_draft.md`（用 `edit` 或 shell 写入均可，只写这一份草稿）。草稿务必已包含「北美热销 TOP5 产品」整段。
3. 调用 `overseas.render_report_or_fallback`，**只传文件路径参数**，让工具一次性完成校验/兜底并落盘两个目标文件：
   - `clusters_path="Lab-04-Overseas-Insights/output/clusters/hotspots.json"`
   - `insights_path="Lab-04-Overseas-Insights/output/insights/insights.json"`
   - `products_path="Lab-04-Overseas-Insights/output/products/top_products.json"`
   - `draft_path="/tmp/gh-aw/agent/report_draft.md"`
   - `out_path="Lab-04-Overseas-Insights/output/report.md"`
   - `frontend_out_path="Lab-04-Overseas-Insights/frontend/report.md"`
   工具会把最终 Markdown **同时写入** `out_path` 与 `frontend_out_path`，并返回精简状态（mode/字数/路径）。**不要再用 `edit` 重复写这两个文件。**（兜底渲染会用 products_path 自动补出 TOP5 表。）
4. 通过 safe-outputs 的 `create-pull-request` 机制提交包含 `Lab-04-Overseas-Insights/output/report.md` 和
   `Lab-04-Overseas-Insights/frontend/report.md` 的 PR。PR 标题应包含日期和报告摘要。
5. 最终总结需说明报告输出路径、前端同步路径和 PR 编号。如使用了兜底逻辑请注明。
