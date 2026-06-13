#!/usr/bin/env python3
"""本地诊断驱动：模拟 overseas-insight 工作流中 AI agent 的 4 阶段编排。

不依赖 GitHub Actions / Copilot LLM。阶段 2/3/4 的 LLM 草稿传空串，
触发 *_or_fallback 的确定性兜底逻辑，用于验证整条 Python 工具链能否在本地跑通。

从仓库根目录运行：
    python Lab-04-Overseas-Insights/run_local_pipeline.py
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

# 仓库根目录（脚本位于 Lab-04-Overseas-Insights/ 下）
REPO_ROOT = Path(__file__).resolve().parents[1]
LAB_DIR = REPO_ROOT / "Lab-04-Overseas-Insights"
SCRIPTS_DIR = LAB_DIR / "mcp-scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from overseas_insight_tools import (  # noqa: E402
    overseas_cluster_or_fallback,
    overseas_fetch_all_to_disk,
    overseas_insight_or_fallback,
    overseas_load_articles_from_disk,
    overseas_read_source_list,
    overseas_render_report_or_fallback,
)

# 工作流默认参数（与 .github/workflows/overseas-insight.md 一致）
SOURCE_LIST_PATH = "Lab-04-Overseas-Insights/input/api/source_list.json"
SIGNALS_DIR = "Lab-04-Overseas-Insights/output/signals"
OUTPUT_DIR = "Lab-04-Overseas-Insights/output"
TIME_WINDOW_HOURS = 72
TOP_K = 6
MAX_ITEMS_PER_SOURCE = 5
TIMEOUT_SECONDS = 15
MAX_CHARS = 200000


def _hr(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70, flush=True)


def _write(rel_path: str, text: str) -> str:
    p = REPO_ROOT / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return str(p.relative_to(REPO_ROOT))


def main() -> int:
    import os

    os.chdir(REPO_ROOT)
    print(f"[cwd] {Path.cwd()}")

    diag: dict[str, object] = {}

    # ---------------- 阶段 1：抓取并装载原始信号 ----------------
    _hr("阶段 1：抓取并装载原始信号")

    src = overseas_read_source_list(source_list_path=SOURCE_LIST_PATH)
    print(f"[read_source_list] 源数量: {src.get('count')}")
    diag["source_count"] = src.get("count")

    t0 = time.time()
    fetch = overseas_fetch_all_to_disk(
        source_list_path=SOURCE_LIST_PATH,
        signals_dir=SIGNALS_DIR,
        timeout_seconds=TIMEOUT_SECONDS,
        max_chars=MAX_CHARS,
        max_items_per_source=MAX_ITEMS_PER_SOURCE,
    )
    print(
        f"[fetch_all_to_disk] 抓取 {fetch.get('fetched')} 个基线源, "
        f"成功 {fetch.get('ok')} 个, 跳过(research-only) {len(fetch.get('research_only_skipped') or [])} 个, "
        f"耗时 {time.time() - t0:.1f}s"
    )
    diag["fetch_total"] = fetch.get("fetched")
    diag["fetch_ok"] = fetch.get("ok")

    raw_signals = overseas_load_articles_from_disk(
        signals_dir=SIGNALS_DIR,
        source_list_path=SOURCE_LIST_PATH,
        max_items_per_source=MAX_ITEMS_PER_SOURCE,
        time_window_hours=TIME_WINDOW_HOURS,
    )
    items = raw_signals.get("items") or []
    print(f"[load_articles_from_disk] 时间窗 {TIME_WINDOW_HOURS}h 内文章: {len(items)} 条")
    diag["raw_items"] = len(items)
    # 抽样确认 category / market 标签已写入
    sample_tracks = [it.get("tracks") for it in items[:3]]
    print(f"[抽样 tracks] {json.dumps(sample_tracks, ensure_ascii=False)}")

    raw_signals_json = json.dumps(raw_signals, ensure_ascii=False, default=str)
    p1 = _write("Lab-04-Overseas-Insights/output/raw_signals.json", raw_signals_json + "\n")
    print(f"[落盘] {p1}")

    # ---------------- 阶段 2：聚类（fallback 路径）----------------
    _hr("阶段 2：聚类热点（本地无 LLM -> fallback）")
    clusters = overseas_cluster_or_fallback(
        raw_signals_json=raw_signals_json,
        clusters_json="",  # 本地无 LLM，触发 fallback
        top_k=TOP_K,
    )
    hotspots = clusters.get("hotspots") or []
    print(f"[cluster_or_fallback] mode={clusters.get('mode')} 热点数: {len(hotspots)}")
    diag["cluster_mode"] = clusters.get("mode")
    diag["hotspots"] = len(hotspots)

    clusters_json = json.dumps(clusters, ensure_ascii=False, default=str)
    p2 = _write("Lab-04-Overseas-Insights/output/clusters/hotspots.json", clusters_json + "\n")
    print(f"[落盘] {p2}")

    # ---------------- 阶段 3：洞察（fallback 路径）----------------
    _hr("阶段 3：生成热点洞察（本地无 LLM -> fallback）")
    insights = overseas_insight_or_fallback(
        clusters_json=clusters_json,
        insights_json="",  # 本地无 LLM，触发 fallback
    )
    insights_list = insights.get("insights") or []
    print(f"[insight_or_fallback] mode={insights.get('mode')} 洞察数: {len(insights_list)}")
    diag["insight_mode"] = insights.get("mode")
    diag["insights"] = len(insights_list)

    insights_json = json.dumps(insights, ensure_ascii=False, default=str)
    p3 = _write("Lab-04-Overseas-Insights/output/insights/insights.json", insights_json + "\n")
    print(f"[落盘] {p3}")

    # ---------------- 阶段 4：报告（fallback 路径）----------------
    _hr("阶段 4：生成并提交 Markdown 报告（本地无 LLM -> fallback）")
    report_md = overseas_render_report_or_fallback(
        clusters_json=clusters_json,
        insights_json=insights_json,
        draft_markdown="",  # 本地无 LLM，触发 fallback
    )
    print(f"[render_report_or_fallback] 报告长度: {len(report_md)} chars")
    diag["report_chars"] = len(report_md)

    p4a = _write("Lab-04-Overseas-Insights/output/report.md", report_md)
    p4b = _write("Lab-04-Overseas-Insights/frontend/report.md", report_md)
    print(f"[落盘] {p4a}")
    print(f"[落盘] {p4b}")

    # ---------------- 诊断汇总 ----------------
    _hr("诊断汇总")
    print(json.dumps(diag, ensure_ascii=False, indent=2))

    ok = (
        diag.get("source_count")
        and (diag.get("hotspots") or 0) >= 0
        and (diag.get("report_chars") or 0) > 0
    )
    print(f"\n[结果] 流水线执行: {'成功 ✅' if ok else '存在问题 ❌'}")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        print("\n[FATAL] 流水线执行异常：", flush=True)
        traceback.print_exc()
        raise SystemExit(2)
