#!/usr/bin/env python3
"""MCP Script: wraps overseas.read_source_list for gh-aw."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from overseas_insight_tools import overseas_read_source_list


def _print_result(result: object) -> None:
    if isinstance(result, str):
        print(result)
    else:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        raw = sys.stdin.read().strip()
        kwargs = json.loads(raw) if raw else {}
        result = overseas_read_source_list(**kwargs)
        _print_result(result)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)
