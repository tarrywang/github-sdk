#!/usr/bin/env python3
"""File I/O tools used by MCP Script wrappers (e.g. write_text_file.py)."""

from __future__ import annotations

from pathlib import Path


def write_text_file(
    path: str, text: str, overwrite: bool = True, encoding: str = "utf-8"
) -> str:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)

    if p.exists() and not overwrite:
        raise FileExistsError(str(p))

    p.write_text(text or "", encoding=encoding)
    return str(p)
