from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import httpx


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_key(s: str, *, max_len: int = 64) -> str:
    s = (s or "").strip()
    if not s:
        return "source"
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9_\-\.\u4e00-\u9fff]+", "_", s)
    s = s.strip("_-")
    return s[:max_len] or "source"


def _read_json(path: str | Path) -> Any:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def _as_list_of_sources(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        platforms = payload.get("platforms")
        if isinstance(platforms, list):
            return [x for x in platforms if isinstance(x, dict)]
    raise ValueError("Invalid source list JSON: expected list or {platforms:[...]}.")


def _to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None

    # RFC822 / RFC2822
    try:
        dt = parsedate_to_datetime(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass

    # ISO8601 (best-effort)
    try:
        s2 = s.replace("Z", "+00:00")
        dt2 = datetime.fromisoformat(s2)
        return dt2 if dt2.tzinfo else dt2.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _normalize_title(title: str) -> str:
    t = (title or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _domain(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def _signal_weight(level: str | None) -> int:
    v = (level or "").strip().upper()
    return {"S": 30, "A": 20, "B": 10}.get(v, 0)


def _derive_tracks(source: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    inc = source.get("include_keywords")
    if isinstance(inc, list):
        for k in inc:
            if isinstance(k, str) and k.strip():
                keys.append(k.strip().lower())

    # Coarse buckets from keywords (EV themes).
    joined = " ".join(keys)
    tracks: list[str] = []
    if any(
        x in joined
        for x in [
            "battery",
            "电池",
            "charging",
            "充电",
            "solid-state",
            "固态",
            "autonomous",
            "自动驾驶",
            "adas",
            "智能驾驶",
        ]
    ):
        tracks.append("tech_battery")
    if any(
        x in joined
        for x in [
            "sales",
            "销量",
            "delivery",
            "交付",
            "policy",
            "政策",
            "subsidy",
            "补贴",
            "tariff",
            "关税",
        ]
    ):
        tracks.append("market_policy")
    if any(
        x in joined for x in ["launch", "新车", "model", "车型", "release", "发布"]
    ):
        tracks.append("new_model")
    if not tracks:
        # fallback by domain / platform
        platform = str(source.get("platform") or "").lower()
        dom = _domain(str(source.get("url") or ""))
        if any(
            x in dom or x in platform
            for x in ["cnevpost", "carnewschina", "pandaily"]
        ):
            tracks.append("china_ev")
        elif any(
            x in dom or x in platform
            for x in ["electrek", "insideevs", "cleantechnica", "thedriven", "chargedevs"]
        ):
            tracks.append("global_ev")
        else:
            tracks.append("auto_news")
    return sorted(set(tracks))


def _guess_language(text: str) -> str | None:
    # Very small heuristic to support zh/en split.
    s = text or ""
    if not s.strip():
        return None
    has_zh = bool(re.search(r"[\u4e00-\u9fff]", s))
    has_en = bool(re.search(r"[A-Za-z]", s))
    if has_zh and has_en:
        return "mixed"
    if has_zh:
        return "zh"
    if has_en:
        return "en"
    return None


def _safe_excerpt(text: str, *, max_len: int = 260) -> str:
    s = (text or "").strip()
    s = re.sub(r"\s+", " ", s)
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


@dataclass
class ArticleItem:
    platform: str
    platform_key: str
    source_type: str
    title: str
    title_norm: str
    url: str
    published_at: str | None
    published_ts: float | None
    summary: str
    company: str | None
    signal_level: str | None
    include_keywords: list[str]
    tracks: list[str]
    language: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "platform_key": self.platform_key,
            "source_type": self.source_type,
            "title": self.title,
            "title_norm": self.title_norm,
            "url": self.url,
            "published_at": self.published_at,
            "summary": self.summary,
            "company": self.company,
            "signal_level": self.signal_level,
            "include_keywords": list(self.include_keywords),
            "tracks": list(self.tracks),
            "language": self.language,
        }


def tech_read_source_list(
    source_list_path: str = "input/api/rss_list.json",
) -> dict[str, Any]:
    payload = _read_json(source_list_path)
    sources = _as_list_of_sources(payload)
    out: list[dict[str, Any]] = []
    for s in sources:
        url = str(s.get("url") or "").strip()
        if not url:
            continue
        platform = str(s.get("platform") or s.get("name") or s.get("id") or url).strip()
        out.append(
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "platform": platform,
                "source": s.get("source") or "rss",
                "url": url,
                "company": s.get("company"),
                "signal_level": s.get("signal_level"),
                "include_keywords": s.get("include_keywords")
                if isinstance(s.get("include_keywords"), list)
                else [],
            }
        )
    return {"source_list_path": source_list_path, "count": len(out), "sources": out}


def tech_fetch_all_to_disk(
    *,
    source_list_path: str = "input/api/rss_list.json",
    output_dir: str = "./output/signals",
    signals_dir: str | None = None,
    timeout_seconds: int = 20,
    max_chars: int = 200000,
    max_items_per_source: int = 25,
) -> dict[str, Any]:
    """Fetch raw payloads from RSS/Sitemap/HTML sources and store them under signals_dir.

    This tool intentionally stores the raw response; parsing happens in tech.load_articles_from_disk.
    """

    del max_items_per_source  # kept for parity with workflow args

    # signals_dir is an alias for output_dir
    if signals_dir is not None:
        output_dir = signals_dir

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    src_payload = tech_read_source_list(source_list_path)
    sources = src_payload.get("sources")
    if not isinstance(sources, list):
        sources = []

    results: list[dict[str, Any]] = []

    headers = {
        "User-Agent": "GCR-AI-Tour-2026/tech_insight_workflow (+https://github.com)"
    }

    total = len(sources)
    print(
        f"[tech.fetch_all_to_disk] Fetching {total} sources (timeout={timeout_seconds}s)...",
        flush=True,
    )

    with httpx.Client(
        timeout=timeout_seconds, headers=headers, follow_redirects=True
    ) as client:
        for idx, s in enumerate(sources, start=1):
            if not isinstance(s, dict):
                continue
            url = str(s.get("url") or "").strip()
            if not url:
                continue

            platform = str(s.get("platform") or "source")
            key = _safe_key(platform)
            source_type = str(s.get("source") or "rss").strip().lower()
            ext = {"rss": "xml", "sitemap": "xml", "html": "html"}.get(
                source_type, "txt"
            )
            raw_path = out_dir / f"{key}.{ext}"
            meta_path = out_dir / f"{key}.meta.json"

            item: dict[str, Any] = {
                "platform": platform,
                "platform_key": key,
                "source": source_type,
                "url": url,
                "raw_path": str(raw_path),
                "ok": False,
                "status_code": None,
                "error": None,
                "fetched_at": _to_iso(_utc_now()),
            }

            print(
                f"  [{idx}/{total}] {platform} ({source_type})...", end=" ", flush=True
            )
            start_time = time.time()
            try:
                r = client.get(url)
                item["status_code"] = int(r.status_code)
                text = r.text
                if (
                    isinstance(max_chars, int)
                    and max_chars > 0
                    and len(text) > max_chars
                ):
                    text = text[:max_chars]
                raw_path.write_text(text, encoding="utf-8")
                meta_path.write_text(
                    json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                item["ok"] = 200 <= int(r.status_code) < 400
                elapsed = time.time() - start_time
                print(
                    f"OK ({r.status_code}, {len(text)} chars, {elapsed:.1f}s)",
                    flush=True,
                )
            except Exception as exc:
                elapsed = time.time() - start_time
                item["error"] = str(exc)
                err_msg = str(exc)[:60]
                print(f"FAIL ({err_msg}, {elapsed:.1f}s)", flush=True)
                try:
                    raw_path.write_text(f"ERROR: {exc}\nURL: {url}\n", encoding="utf-8")
                except Exception:
                    pass
                try:
                    meta_path.write_text(
                        json.dumps(s, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                except Exception:
                    pass

            results.append(item)
            time.sleep(0.05)

    ok_count = sum(1 for x in results if x.get("ok"))
    print(
        f"[tech.fetch_all_to_disk] Done: {ok_count}/{len(results)} sources fetched successfully.",
        flush=True,
    )
    return {
        "source_list_path": source_list_path,
        "output_dir": str(out_dir),
        "fetched": len(results),
        "ok": ok_count,
        "results": results,
    }


def _parse_rss_items(raw: str, *, max_items: int) -> list[dict[str, Any]]:
    try:
        import feedparser  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Missing dependency: feedparser. Install with requirements.txt"
        ) from exc

    parsed = feedparser.parse(raw.encode("utf-8", errors="ignore"))
    entries = getattr(parsed, "entries", None) or []
    out: list[dict[str, Any]] = []
    for e in entries[: max(1, int(max_items or 25))]:
        if not isinstance(e, dict):
            continue
        title = str(e.get("title") or "").strip()
        url = str(e.get("link") or e.get("id") or "").strip()
        summary = str(e.get("summary") or e.get("description") or "").strip()

        dt: datetime | None = None
        for k in ["published", "updated", "created"]:
            dt = _parse_datetime(e.get(k))
            if dt:
                break
        if not dt:
            for k in ["published_parsed", "updated_parsed"]:
                v = e.get(k)
                try:
                    if v:
                        dt = datetime(*v[:6], tzinfo=timezone.utc)
                        break
                except Exception:
                    dt = None

        out.append(
            {
                "title": title,
                "url": url,
                "summary": summary,
                "published_dt": dt,
            }
        )
    return out


def _parse_sitemap_items(raw: str, *, max_items: int) -> list[dict[str, Any]]:
    import xml.etree.ElementTree as ET

    out: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(raw)
    except Exception:
        return out

    # Handle namespaces by stripping.
    def _strip_ns(tag: str) -> str:
        return tag.split("}")[-1] if "}" in tag else tag

    rows: list[dict[str, Any]] = []
    for url_node in root.iter():
        if _strip_ns(url_node.tag) != "url":
            continue
        loc = None
        lastmod = None
        for child in list(url_node):
            t = _strip_ns(child.tag)
            if t == "loc":
                loc = (child.text or "").strip()
            elif t == "lastmod":
                lastmod = (child.text or "").strip()
        if loc:
            rows.append(
                {
                    "title": "",
                    "url": loc,
                    "summary": "",
                    "published_dt": _parse_datetime(lastmod),
                }
            )

    rows.sort(
        key=lambda r: (
            r.get("published_dt") or datetime(1970, 1, 1, tzinfo=timezone.utc)
        ),
        reverse=True,
    )
    for r in rows[: max(1, int(max_items or 25))]:
        out.append(r)
    return out


def _parse_html_listing_items(
    raw: str, base_url: str, *, max_items: int
) -> list[dict[str, Any]]:
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Missing dependency: beautifulsoup4. Install with requirements.txt"
        ) from exc

    soup = BeautifulSoup(raw, "html.parser")
    links: list[tuple[str, str]] = []

    base_dom = _domain(base_url)
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue
        href = str(href).strip()
        if not href.startswith("http"):
            continue
        if base_dom and _domain(href) and _domain(href) != base_dom:
            continue
        text = (a.get_text() or "").strip()
        links.append((href, text))

    # De-dupe by URL, keep first text.
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for href, text in links:
        if href in seen:
            continue
        seen.add(href)
        title = text or href.split("/")[-1] or href
        out.append({"title": title, "url": href, "summary": "", "published_dt": None})
        if len(out) >= max(1, int(max_items or 25)):
            break
    return out


def tech_load_articles_from_disk(
    *,
    signals_dir: str,
    source_list_path: str = "input/api/rss_list.json",
    max_items_per_source: int = 25,
    time_window_hours: int = 24,
) -> dict[str, Any]:
    src_payload = tech_read_source_list(source_list_path)
    sources = src_payload.get("sources")
    if not isinstance(sources, list):
        sources = []

    sig_dir = Path(signals_dir)
    now = _utc_now()
    cutoff = now - timedelta(hours=float(time_window_hours or 24))

    out_sources: list[dict[str, Any]] = []
    items: list[ArticleItem] = []

    for s in sources:
        if not isinstance(s, dict):
            continue

        url = str(s.get("url") or "").strip()
        platform = str(s.get("platform") or "source")
        key = _safe_key(platform)
        source_type = str(s.get("source") or "rss").strip().lower()
        ext = {"rss": "xml", "sitemap": "xml", "html": "html"}.get(source_type, "txt")
        raw_path = sig_dir / f"{key}.{ext}"

        company = s.get("company")
        company = (
            str(company).strip()
            if isinstance(company, str) and company.strip()
            else None
        )

        signal_level = s.get("signal_level")
        signal_level = (
            str(signal_level).strip().upper()
            if isinstance(signal_level, str) and signal_level.strip()
            else None
        )

        include_keywords: list[str] = []
        if isinstance(s.get("include_keywords"), list):
            for k in s["include_keywords"]:
                if isinstance(k, str) and k.strip():
                    include_keywords.append(k.strip())

        tracks = _derive_tracks(s)

        raw_text = ""
        try:
            raw_text = raw_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            raw_text = ""

        parsed_rows: list[dict[str, Any]] = []
        parse_error: str | None = None
        try:
            if source_type in {"rss", "atom"}:
                parsed_rows = _parse_rss_items(raw_text, max_items=max_items_per_source)
            elif source_type == "sitemap":
                parsed_rows = _parse_sitemap_items(
                    raw_text, max_items=max_items_per_source
                )
            elif source_type == "html":
                parsed_rows = _parse_html_listing_items(
                    raw_text, url, max_items=max_items_per_source
                )
            else:
                parsed_rows = _parse_rss_items(raw_text, max_items=max_items_per_source)
        except Exception as exc:
            parse_error = str(exc)
            parsed_rows = []

        kept = 0
        for row in parsed_rows:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            link = str(row.get("url") or "").strip()
            if not title and not link:
                continue
            if not link:
                continue

            dt = row.get("published_dt")
            if isinstance(dt, datetime) and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if isinstance(dt, datetime):
                if dt < cutoff:
                    continue
                published_ts = dt.timestamp()
                published_at = _to_iso(dt)
            else:
                published_ts = None
                published_at = None

            summary = str(row.get("summary") or "").strip()
            title_norm = _normalize_title(title or link)
            language = _guess_language(title + " " + summary)

            items.append(
                ArticleItem(
                    platform=platform,
                    platform_key=key,
                    source_type=source_type,
                    title=title or link,
                    title_norm=title_norm,
                    url=link,
                    published_at=published_at,
                    published_ts=published_ts,
                    summary=_safe_excerpt(summary, max_len=100),
                    company=company,
                    signal_level=signal_level,
                    include_keywords=include_keywords,
                    tracks=tracks,
                    language=language,
                )
            )
            kept += 1
            if kept >= max(1, int(max_items_per_source or 25)):
                break

        out_sources.append(
            {
                "platform": platform,
                "platform_key": key,
                "source_type": source_type,
                "url": url,
                "file": str(raw_path),
                "parsed": len(parsed_rows),
                "kept": kept,
                "parse_error": parse_error,
                "company": company,
                "signal_level": signal_level,
                "tracks": tracks,
            }
        )

    # Compute comparable deterministic score for sorting.
    def _item_score(it: ArticleItem) -> float:
        w = _signal_weight(it.signal_level)
        rec = 0.0
        if it.published_ts:
            # 0..24h -> 20..0 (linear decay)
            age_h = max(0.0, (now.timestamp() - it.published_ts) / 3600.0)
            rec = max(
                0.0,
                20.0
                * (
                    1.0
                    - min(age_h, float(time_window_hours or 24))
                    / float(time_window_hours or 24)
                ),
            )
        return float(w) + rec

    items.sort(key=_item_score, reverse=True)

    return {
        "window": {
            "time_window_hours": int(time_window_hours or 24),
            "cutoff": _to_iso(cutoff),
            "generated_at": _to_iso(now),
        },
        "sources": out_sources,
        "items": [it.as_dict() for it in items],
    }


def _read_if_path(s: Any) -> Any:
    """If the value looks like a path to an existing file (rather than inline
    JSON), return the file's contents. Makes the tools tolerant of the agent
    passing a file path instead of the actual JSON content."""
    if isinstance(s, str):
        t = s.strip()
        if t and t[0] not in "{[" and "\n" not in t and len(t) <= 1024:
            try:
                p = Path(t)
                if p.is_file():
                    return p.read_text(encoding="utf-8")
            except OSError:
                pass
    return s


def _extract_json(text: str) -> Any:
    text = _read_if_path(text)
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"```\s*$", "", t)
    # Find first JSON object or array.
    start_obj = t.find("{")
    start_arr = t.find("[")
    start = min([x for x in [start_obj, start_arr] if x != -1], default=-1)
    if start == -1:
        raise ValueError("No JSON found")
    end_obj = t.rfind("}")
    end_arr = t.rfind("]")
    end = max(end_obj, end_arr)
    if end == -1 or end <= start:
        raise ValueError("No JSON found")
    return json.loads(t[start : end + 1])


def _coerce_raw_signals(raw_signals_json: str) -> dict[str, Any]:
    raw_signals_json = _read_if_path(raw_signals_json)
    obj = (
        json.loads(raw_signals_json)
        if isinstance(raw_signals_json, str)
        else raw_signals_json
    )
    if not isinstance(obj, dict):
        raise ValueError("raw_signals_json must be a JSON object")
    return obj


def _similar(a: str, b: str) -> float:
    from difflib import SequenceMatcher

    return float(SequenceMatcher(None, a or "", b or "").ratio())


def _fallback_cluster(items: list[dict[str, Any]], *, top_k: int) -> dict[str, Any]:
    clusters: list[dict[str, Any]] = []

    def item_score(it: dict[str, Any]) -> float:
        w = _signal_weight(str(it.get("signal_level") or ""))
        rec = 0.0
        ts = None
        published_at = it.get("published_at")
        dt = _parse_datetime(published_at)
        if dt:
            ts = dt.timestamp()
        if ts:
            age_h = max(0.0, (_utc_now().timestamp() - ts) / 3600.0)
            rec = max(0.0, 10.0 * (1.0 - min(age_h, 24.0) / 24.0))
        cov = 0.0
        if it.get("company"):
            cov += 2.0
        return float(w) + rec + cov

    items_sorted = sorted(items, key=item_score, reverse=True)

    for it in items_sorted:
        title_norm = str(
            it.get("title_norm") or _normalize_title(str(it.get("title") or ""))
        )
        company = str(it.get("company") or "").strip() or None
        tracks_val = it.get("tracks")
        tracks = tracks_val if isinstance(tracks_val, list) else []
        tracks_set = {str(x) for x in tracks if isinstance(x, str) and x}

        best_idx = None
        best_sim = 0.0
        for idx, c in enumerate(clusters):
            c_title = str(c.get("_title_norm") or "")
            c_company = c.get("_company")
            c_tracks = c.get("_tracks") if isinstance(c.get("_tracks"), set) else set()

            sim = _similar(title_norm, c_title)
            threshold = 0.78
            if company and c_company and company == c_company:
                threshold = 0.72
            if tracks_set and c_tracks and (tracks_set & c_tracks):
                threshold = min(threshold, 0.74)

            if sim >= threshold and sim > best_sim:
                best_sim = sim
                best_idx = idx

        if best_idx is None:
            clusters.append(
                {
                    "_title_norm": title_norm,
                    "_company": company,
                    "_tracks": set(tracks_set),
                    "items": [it],
                }
            )
        else:
            clusters[best_idx]["items"].append(it)
            if tracks_set:
                clusters[best_idx]["_tracks"].update(tracks_set)

    hotspots: list[dict[str, Any]] = []
    for i, c in enumerate(clusters, start=1):
        c_items: list[dict[str, Any]] = list(c.get("items") or [])
        platforms = sorted(
            {str(x.get("platform") or "") for x in c_items if x.get("platform")}
        )
        companies = sorted(
            {str(x.get("company") or "") for x in c_items if x.get("company")}
        )

        # Heuristic scoring.
        signal_max = max(
            (_signal_weight(str(x.get("signal_level") or "")) for x in c_items),
            default=0,
        )
        coverage = len(
            {(x.get("platform_key") or x.get("platform") or "") for x in c_items}
        )
        size = len(c_items)
        score = 40.0
        score += 10.0 * math.log1p(size)
        score += 8.0 * float(coverage)
        score += 0.5 * float(signal_max)
        if companies:
            score += 5.0

        # Determine category.
        category = "trend" if coverage >= 2 or size >= 3 else "single"
        if signal_max >= 20 and coverage == 1 and size <= 2:
            category = "single"

        # should_chase: prioritize high signal and/or coverage.
        should_chase = (
            "yes" if (score >= 65.0 or signal_max >= 20 or coverage >= 3) else "no"
        )

        title = str(c_items[0].get("title") or "(untitled)") if c_items else "(empty)"
        summary_bits: list[str] = []
        if companies:
            summary_bits.append(f"company={', '.join(companies[:3])}")
        tracks = sorted(
            {t for x in c_items for t in (x.get("tracks") or []) if isinstance(t, str)}
        )
        if tracks:
            summary_bits.append(f"tracks={', '.join(tracks[:4])}")
        summary = "；".join(summary_bits) or "自动聚类生成的主题。"

        samples = []
        for x in c_items[: max(1, min(5, len(c_items)))]:
            samples.append(
                {
                    "platform": x.get("platform"),
                    "title": x.get("title"),
                    "url": x.get("url"),
                    "published_at": x.get("published_at"),
                    "company": x.get("company"),
                    "signal_level": x.get("signal_level"),
                }
            )

        hotspots.append(
            {
                "hotspot_id": f"H{i:02d}",
                "title": title,
                "summary": summary,
                "category": category,
                "overall_heat_score": int(round(score)),
                "coverage": {
                    "source_count": int(coverage),
                    "companies": companies,
                    "platforms": platforms,
                },
                "should_chase": should_chase,
                "chase_rationale": [],
                "samples": samples,
            }
        )

    hotspots.sort(key=lambda h: int(h.get("overall_heat_score") or 0), reverse=True)
    hotspots = hotspots[: max(1, int(top_k or 12))]
    return {"mode": "fallback", "top_k": int(top_k or 12), "hotspots": hotspots}


def tech_cluster_or_fallback(
    *, raw_signals_json: str, clusters_json: str, top_k: int = 12
) -> dict[str, Any]:
    raw = _coerce_raw_signals(raw_signals_json)
    items = raw.get("items")
    if not isinstance(items, list):
        items = []

    # Try to accept LLM output.
    llm_obj: Any = None
    mode = "llm"
    try:
        llm_obj = _extract_json(clusters_json)
        if isinstance(llm_obj, list):
            llm_obj = {"hotspots": llm_obj}
        if not (
            isinstance(llm_obj, dict) and isinstance(llm_obj.get("hotspots"), list)
        ):
            raise ValueError("Invalid clusters json")
    except Exception:
        mode = "fallback"
        llm_obj = None

    if mode == "llm" and llm_obj is not None:
        # Light validation: ensure hotspots has required fields.
        sanitized: list[dict[str, Any]] = []
        for idx, h in enumerate(llm_obj.get("hotspots") or [], start=1):
            if not isinstance(h, dict):
                continue
            title = str(h.get("title") or "").strip() or f"Hotspot {idx}"
            sanitized.append(
                {
                    "hotspot_id": str(h.get("hotspot_id") or f"H{idx:02d}"),
                    "title": title,
                    "summary": str(h.get("summary") or ""),
                    "category": str(h.get("category") or "trend"),
                    "overall_heat_score": int(h.get("overall_heat_score") or 0),
                    "coverage": h.get("coverage")
                    if isinstance(h.get("coverage"), dict)
                    else {"source_count": 0, "companies": [], "platforms": []},
                    "should_chase": str(h.get("should_chase") or "no"),
                    "chase_rationale": h.get("chase_rationale")
                    if isinstance(h.get("chase_rationale"), list)
                    else [],
                    "samples": h.get("samples")
                    if isinstance(h.get("samples"), list)
                    else [],
                }
            )
            if len(sanitized) >= int(top_k or 12):
                break
        return {"mode": "llm", "top_k": int(top_k or 12), "hotspots": sanitized}

    return _fallback_cluster(
        [x for x in items if isinstance(x, dict)], top_k=int(top_k or 12)
    )


def tech_insight_or_fallback(
    *, clusters_json: str, insights_json: str
) -> dict[str, Any]:
    # Try LLM insights.
    try:
        llm_obj = _extract_json(insights_json)
        if isinstance(llm_obj, list):
            llm_obj = {"insights": llm_obj}
        if isinstance(llm_obj, dict) and isinstance(llm_obj.get("insights"), list):
            return {"mode": "llm", "insights": llm_obj.get("insights")}
    except Exception:
        pass

    clusters = _extract_json(clusters_json)
    if isinstance(clusters, list):
        clusters = {"hotspots": clusters}
    hotspots = clusters.get("hotspots") if isinstance(clusters, dict) else None
    if not isinstance(hotspots, list):
        hotspots = []

    insights: list[dict[str, Any]] = []
    for h in hotspots:
        if not isinstance(h, dict):
            continue
        hid = str(h.get("hotspot_id") or "")
        title = str(h.get("title") or "")
        category = str(h.get("category") or "trend")
        coverage_val = h.get("coverage")
        coverage = coverage_val if isinstance(coverage_val, dict) else {}
        companies_val = coverage.get("companies")
        companies = companies_val if isinstance(companies_val, list) else []
        platforms_val = coverage.get("platforms")
        platforms = platforms_val if isinstance(platforms_val, list) else []

        what_changed = "".join(
            [
                f"过去 24 小时出现了与“{title}”相关的 EV 行业动态。",
                f"来源覆盖 {len(platforms)} 个源" if platforms else "",
            ]
        ).strip()
        why = "趋势" if category == "trend" else "重要更新"
        why_it_matters = f"这是一条 EV 市场{why}信号，可能影响车企竞争格局、产品策略或采购/投资决策。"
        who = ["车企与产品团队", "供应链与电池厂商", "投资者与分析师"]
        if companies:
            who.append("关注相关车企动态的人群")
        next_actions = [
            "查看引用链接确认原文",
            "评估对自身产品/市场策略的影响",
            "如涉及竞品新车型或降价，跟进竞争分析",
        ]
        risk_notes = []
        insights.append(
            {
                "hotspot_id": hid,
                "title": title,
                "what_changed": what_changed,
                "why_it_matters": why_it_matters,
                "who_is_impacted": who,
                "next_actions": next_actions,
                "risk_notes": risk_notes,
                "references": [],
            }
        )

    return {"mode": "fallback", "insights": insights}


def tech_render_report_or_fallback(
    *,
    clusters_json: str,
    insights_json: str,
    draft_markdown: str,
) -> str:
    md = (draft_markdown or "").strip()
    # If LLM produced a plausible markdown, keep it.
    if md and "(mock" not in md.lower() and len(md) > 120:
        return md.strip() + "\n"

    clusters = _extract_json(clusters_json)
    if isinstance(clusters, list):
        clusters = {"hotspots": clusters}
    hotspots = clusters.get("hotspots") if isinstance(clusters, dict) else None
    if not isinstance(hotspots, list):
        hotspots = []

    insights_obj = None
    try:
        insights_obj = _extract_json(insights_json)
    except Exception:
        insights_obj = None
    insights_list: list[dict[str, Any]] = []
    if isinstance(insights_obj, list):
        insights_list = [x for x in insights_obj if isinstance(x, dict)]
    elif isinstance(insights_obj, dict):
        insights_val = insights_obj.get("insights")
        if isinstance(insights_val, list):
            insights_list = [x for x in insights_val if isinstance(x, dict)]
    by_id = {str(x.get("hotspot_id") or ""): x for x in insights_list}

    trends = [
        h
        for h in hotspots
        if isinstance(h, dict) and str(h.get("category") or "") == "trend"
    ]
    singles = [
        h
        for h in hotspots
        if isinstance(h, dict) and str(h.get("category") or "") != "trend"
    ]

    def _render_hotspot(h: dict[str, Any]) -> str:
        hid = str(h.get("hotspot_id") or "")
        title = str(h.get("title") or "")
        score = str(h.get("overall_heat_score") or "")
        cov_val = h.get("coverage")
        cov = cov_val if isinstance(cov_val, dict) else {}
        companies_val = cov.get("companies")
        companies = companies_val if isinstance(companies_val, list) else []
        platforms_val = cov.get("platforms")
        platforms = platforms_val if isinstance(platforms_val, list) else []
        samples_val = h.get("samples")
        samples = samples_val if isinstance(samples_val, list) else []
        insight = by_id.get(hid) or {}

        lines: list[str] = []
        lines.append(f"### {hid} · {title}")
        if score:
            lines.append(f"- 热度：{score}")
        if companies:
            lines.append(f"- 涉及车企：{', '.join([str(x) for x in companies[:6]])}")
        if platforms:
            lines.append(f"- 来源：{', '.join([str(x) for x in platforms[:8]])}")
        what_changed = str(insight.get("what_changed") or "").strip()
        why_it_matters = str(insight.get("why_it_matters") or "").strip()
        if what_changed:
            lines.append(f"- 发生了什么：{what_changed}")
        if why_it_matters:
            lines.append(f"- 为什么重要：{why_it_matters}")
        if samples:
            lines.append("- 参考链接：")
            for s in samples[:5]:
                if not isinstance(s, dict):
                    continue
                t = str(s.get("title") or "").strip()
                u = str(s.get("url") or "").strip()
                if u:
                    lines.append(f"  - {t} ({u})" if t else f"  - {u}")
        lines.append("")
        return "\n".join(lines)

    company_radar: dict[str, list[dict[str, Any]]] = {}
    for h in hotspots:
        if not isinstance(h, dict):
            continue
        cov_val = h.get("coverage")
        cov = cov_val if isinstance(cov_val, dict) else {}
        companies_val = cov.get("companies")
        companies = companies_val if isinstance(companies_val, list) else []
        for c in companies:
            c2 = str(c).strip()
            if not c2:
                continue
            company_radar.setdefault(c2, []).append(h)

    lines: list[str] = []
    lines.append("# EV 市场洞察报告（兜底版）\n")
    lines.append(f"- 生成时间：{_to_iso(_utc_now())}")
    lines.append("- 时间窗：过去 24 小时")
    lines.append("")

    lines.append("## 跨源趋势\n")
    if not trends:
        lines.append("（未提取到趋势）\n")
    else:
        for h in trends:
            lines.append(_render_hotspot(h))

    lines.append("## 重要单条更新\n")
    if not singles:
        lines.append("（未提取到重要单条更新）\n")
    else:
        for h in singles:
            lines.append(_render_hotspot(h))

    lines.append("## 车企竞争雷达\n")
    if not company_radar:
        lines.append("（暂无可归类到车企的条目）\n")
    else:
        for c, hs in sorted(company_radar.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            lines.append(f"### {c}")
            for h in sorted(
                hs, key=lambda x: int(x.get("overall_heat_score") or 0), reverse=True
            )[:6]:
                hid = str(h.get("hotspot_id") or "")
                title = str(h.get("title") or "")
                lines.append(f"- {hid}: {title}")
            lines.append("")

    lines.append("---\n")
    lines.append("说明：本报告在无 LLM 或 LLM 输出不可解析时，由确定性兜底逻辑生成。\n")
    return "\n".join(lines).strip() + "\n"


def register_tools(registry: object) -> None:
    register = getattr(registry, "register_tool", None)
    if not callable(register):
        return

    register("tech.read_source_list", tech_read_source_list)
    register("tech.fetch_all_to_disk", tech_fetch_all_to_disk)
    register("tech.load_articles_from_disk", tech_load_articles_from_disk)
    register("tech.cluster_or_fallback", tech_cluster_or_fallback)
    register("tech.insight_or_fallback", tech_insight_or_fallback)
    register("tech.render_report_or_fallback", tech_render_report_or_fallback)
