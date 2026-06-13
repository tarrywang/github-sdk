#!/usr/bin/env python3
"""Pre-step runner: fetch the 5 e-commerce bestseller pages via ScraperAPI and
write compact per-site extracts to disk for the agent to read.

Runs as a normal GitHub Actions step (outside the agent firewall sandbox) with
the API key supplied via the SCRAPER_API_KEY secret — so the key never reaches
the agent/LLM. Gracefully no-ops (writes a skip summary) when the key is absent.

Env:
  SCRAPER_API_KEY            ScraperAPI key (required to actually fetch)
  BESTSELLER_SOURCE_LIST     source_list.json path (default repo Lab-04 path)
  BESTSELLER_OUT_DIR         output dir (default Lab-04 signals/bestsellers)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from overseas_insight_tools import overseas_fetch_bestsellers_to_disk

DEFAULT_SOURCE_LIST = "Lab-04-Overseas-Insights/input/api/source_list.json"
DEFAULT_OUT_DIR = "Lab-04-Overseas-Insights/output/signals/bestsellers"


def main() -> int:
    api_key = os.environ.get("SCRAPER_API_KEY", "")
    source_list = os.environ.get("BESTSELLER_SOURCE_LIST", DEFAULT_SOURCE_LIST)
    out_dir = os.environ.get("BESTSELLER_OUT_DIR", DEFAULT_OUT_DIR)

    summary = overseas_fetch_bestsellers_to_disk(
        api_key=api_key,
        source_list_path=source_list,
        out_dir=out_dir,
    )
    # Never fail the build on scrape gaps — bestseller research is best-effort.
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
