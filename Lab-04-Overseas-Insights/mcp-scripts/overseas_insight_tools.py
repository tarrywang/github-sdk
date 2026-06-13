from __future__ import annotations

import html as _htmlmod
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


# 出海市场洞察：品类与目标市场标签
_CATEGORY_LABELS = {"beauty": "美妆护肤", "3c": "3C电子", "jewelry": "饰品配饰"}
_MARKET_LABELS = {"na": "北美", "eu": "欧洲", "sea": "东南亚", "global": "全球"}
_PRODUCT_CATEGORIES = ("beauty", "3c", "jewelry")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_key(s: str, *, max_len: int = 64) -> str:
    s = (s or "").strip()
    if not s:
        return "source"
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9_\-\.一-鿿]+", "_", s)
    s = s.strip("_-")
    return s[:max_len] or "source"


def _read_json(path: str | Path) -> Any:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def _as_list_of_sources(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        platforms = payload.get("platforms") or payload.get("sources")
        if isinstance(platforms, list):
            return [x for x in platforms if isinstance(x, dict)]
    raise ValueError("Invalid source list JSON: expected list or {sources:[...]}.")


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
    t = re.sub(r"[^a-z0-9一-鿿 ]+", " ", t)
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


def _normalize_category(value: Any) -> str | None:
    v = str(value or "").strip().lower()
    if not v:
        return None
    if v in {"beauty", "skincare", "cosmetics", "cosmetic", "makeup", "美妆", "护肤", "彩妆"}:
        return "beauty"
    if v in {"3c", "electronics", "electronic", "tech", "gadget", "gadgets", "数码", "电子", "消费电子"}:
        return "3c"
    if v in {
        "jewelry",
        "jewellery",
        "accessories",
        "accessory",
        "饰品",
        "配饰",
        "珠宝",
        "首饰",
    }:
        return "jewelry"
    return None


def _normalize_markets(value: Any) -> list[str]:
    alias = {
        "na": "na",
        "us": "na",
        "usa": "na",
        "north-america": "na",
        "northamerica": "na",
        "north_america": "na",
        "美国": "na",
        "北美": "na",
        "eu": "eu",
        "europe": "eu",
        "uk": "eu",
        "欧洲": "eu",
        "sea": "sea",
        "southeast-asia": "sea",
        "southeastasia": "sea",
        "southeast_asia": "sea",
        "asean": "sea",
        "东南亚": "sea",
        "global": "global",
        "ww": "global",
        "worldwide": "global",
        "全球": "global",
    }
    raw = value if isinstance(value, list) else [value]
    out: list[str] = []
    for m in raw:
        k = str(m or "").strip().lower()
        mapped = alias.get(k)
        if mapped and mapped not in out:
            out.append(mapped)
    return out


def _derive_tracks(source: dict[str, Any]) -> list[str]:
    """Data-driven track derivation for overseas market research.

    Primary signal: explicit `category` (beauty|3c|jewelry) + `markets` list.
    Emits `<category>` and `market:<m>` tokens. Falls back to keyword/domain
    heuristics only when category/markets are absent.
    """
    tracks: list[str] = []

    category = _normalize_category(source.get("category"))
    markets = _normalize_markets(source.get("markets"))

    if category:
        tracks.append(category)
    for m in markets:
        tracks.append(f"market:{m}")

    keys: list[str] = []
    inc = source.get("include_keywords")
    if isinstance(inc, list):
        for k in inc:
            if isinstance(k, str) and k.strip():
                keys.append(k.strip().lower())
    joined = " ".join(keys)

    if not category:
        # Secondary enrichment from include_keywords.
        if any(
            x in joined
            for x in ["skincare", "cosmetic", "beauty", "makeup", "fragrance", "美妆", "护肤", "彩妆", "香水"]
        ):
            tracks.append("beauty")
        elif any(
            x in joined
            for x in ["phone", "laptop", "gadget", "electronic", "earbud", "wearable", "3c", "数码", "电子", "消费电子"]
        ):
            tracks.append("3c")
        elif any(
            x in joined
            for x in ["jewelry", "jewellery", "accessor", "ring", "necklace", "earring", "饰品", "配饰", "珠宝", "首饰"]
        ):
            tracks.append("jewelry")
        else:
            # Final fallback by domain / platform.
            platform = str(source.get("platform") or "").lower()
            dom = _domain(str(source.get("url") or ""))
            hay = f"{dom} {platform}"
            if any(x in hay for x in ["glossy", "cosmetic", "beauty", "wwd", "premiumbeauty"]):
                tracks.append("beauty")
            elif any(
                x in hay
                for x in ["verge", "engadget", "gsmarena", "androidauthority", "notebookcheck"]
            ):
                tracks.append("3c")
            elif any(x in hay for x in ["jck", "jeweler", "jeweller", "rapaport"]):
                tracks.append("jewelry")
            else:
                tracks.append("market_general")

    return sorted(set(tracks))


def _guess_language(text: str) -> str | None:
    # Very small heuristic to support zh/en split.
    s = text or ""
    if not s.strip():
        return None
    has_zh = bool(re.search(r"[一-鿿]", s))
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
    category: str | None
    markets: list[str]

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
            "category": self.category,
            "markets": list(self.markets),
        }


def overseas_read_source_list(
    source_list_path: str = "input/api/source_list.json",
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
                "category": _normalize_category(s.get("category")),
                "markets": _normalize_markets(s.get("markets")),
                "fetchable": s.get("fetchable") or "rss",
                "include_keywords": s.get("include_keywords")
                if isinstance(s.get("include_keywords"), list)
                else [],
            }
        )
    return {"source_list_path": source_list_path, "count": len(out), "sources": out}


def overseas_fetch_all_to_disk(
    *,
    source_list_path: str = "input/api/source_list.json",
    output_dir: str = "./output/signals",
    signals_dir: str | None = None,
    timeout_seconds: int = 20,
    max_chars: int = 200000,
    max_items_per_source: int = 25,
) -> dict[str, Any]:
    """Fetch raw payloads from RSS/Sitemap/HTML sources and store them under signals_dir.

    This tool intentionally stores the raw response; parsing happens in
    overseas.load_articles_from_disk. Sources tagged ``fetchable: research-only``
    (bot-blocked marketplaces) are skipped here — the agent reaches those via
    deep web research, not this baseline fetcher.
    """

    del max_items_per_source  # kept for parity with workflow args

    # signals_dir is an alias for output_dir
    if signals_dir is not None:
        output_dir = signals_dir

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    src_payload = overseas_read_source_list(source_list_path)
    sources = src_payload.get("sources")
    if not isinstance(sources, list):
        sources = []

    results: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    headers = {
        "User-Agent": "github-sdk/overseas_insight_workflow (+https://github.com)"
    }

    fetchable_sources = [
        s
        for s in sources
        if isinstance(s, dict)
        and str(s.get("fetchable") or "rss").strip().lower() != "research-only"
    ]
    for s in sources:
        if isinstance(s, dict) and str(s.get("fetchable") or "").strip().lower() == "research-only":
            skipped.append({"platform": s.get("platform"), "url": s.get("url")})

    total = len(fetchable_sources)
    print(
        f"[overseas.fetch_all_to_disk] Fetching {total} baseline sources "
        f"(timeout={timeout_seconds}s, research-only skipped={len(skipped)})...",
        flush=True,
    )

    with httpx.Client(
        timeout=timeout_seconds, headers=headers, follow_redirects=True
    ) as client:
        for idx, s in enumerate(fetchable_sources, start=1):
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
        f"[overseas.fetch_all_to_disk] Done: {ok_count}/{len(results)} baseline sources fetched.",
        flush=True,
    )
    return {
        "source_list_path": source_list_path,
        "output_dir": str(out_dir),
        "fetched": len(results),
        "ok": ok_count,
        "research_only_skipped": skipped,
        "results": results,
    }


def _clean_visible_text(html: str) -> str:
    """Strip script/style/etc, drop tags, decode entities, collapse whitespace."""
    html = re.sub(
        r"<(script|style|noscript|svg|template)[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    t = re.sub(r"<[^>]+>", " ", html)
    t = _htmlmod.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def _extract_bestseller_snippet(
    html: str, *, max_chars: int = 2800
) -> dict[str, Any]:
    """Pull a compact, model-friendly extract from a rendered bestseller page:
    product-name candidates (from img alt), ratings, review-count-ish numbers,
    prices, and an ordered text window anchored on the product list. No data is
    invented — empty lists mean the page did not expose it."""
    text = _clean_visible_text(html)

    alts = [_htmlmod.unescape(a) for a in re.findall(r'alt="([^"]{12,140})"', html)]
    bad = re.compile(
        r"logo|icon|sprite|sign in|banner|advertis|prime\b|^\s*$|^image$|placeholder",
        re.IGNORECASE,
    )
    names: list[str] = []
    seen: set[str] = set()
    for a in alts:
        a = a.strip()
        if not a or bad.search(a):
            continue
        if a not in seen:
            seen.add(a)
            names.append(a)
        if len(names) >= 20:
            break

    ratings = re.findall(r"(\d\.\d)\s*out of 5", text)[:25]
    prices = re.findall(r"\$\d[\d,]*(?:\.\d{2})?", text)[:25]

    anchor = text.find("out of 5")
    if anchor == -1:
        anchor = text.lower().find("best seller")
    if anchor == -1:
        anchor = 0
    start = max(0, anchor - 300)
    window = text[start : start + max_chars]

    return {
        "name_candidates": names,
        "ratings": ratings,
        "prices": prices,
        "text_window": window,
    }


def overseas_fetch_bestsellers_to_disk(
    *,
    api_key: str,
    source_list_path: str = "input/api/source_list.json",
    out_dir: str = "./output/signals/bestsellers",
    render: bool = True,
    country: str = "us",
    timeout_seconds: int = 70,
    max_chars: int = 2800,
) -> dict[str, Any]:
    """Fetch the 5 e-commerce bestseller pages through a ScraperAPI-style proxy
    (renders JS + rotates proxies) and write a compact per-site extract to disk.

    Designed to run as a pre-step with the API key from a GitHub secret, so the
    key never enters the agent/LLM sandbox. Protected domains that the current
    proxy plan cannot reach (e.g. Sephora/TikTok on the free tier) are recorded
    as gaps — never fabricated. Returns a small summary (no raw HTML)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    api_key = (api_key or "").strip()
    src = overseas_read_source_list(source_list_path)
    raw_sources = _as_list_of_sources(_read_json(source_list_path))
    # keep declaration order; pick bestseller research targets
    targets = [
        s
        for s in raw_sources
        if isinstance(s, dict)
        and str(s.get("research_kind") or "").strip().lower() == "bestseller"
    ]
    del src

    summary: dict[str, Any] = {
        "provider": "scraperapi",
        "fetched_at": _to_iso(_utc_now()),
        "out_dir": str(out),
        "have_key": bool(api_key),
        "results": [],
    }

    if not api_key:
        summary["note"] = (
            "未配置 SCRAPER_API_KEY，跳过电商榜单抓取；TOP5 将由新闻信号兜底。"
        )
        (out / "_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("[bestsellers] no SCRAPER_API_KEY -> skipped all targets", flush=True)
        return summary

    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        for s in targets:
            platform = str(s.get("platform") or "site").strip()
            key = _safe_key(platform)
            url = str(s.get("url") or "").strip()
            entry: dict[str, Any] = {
                "platform": platform,
                "url": url,
                "status": None,
                "ok": False,
                "names": 0,
                "ratings": 0,
                "note": None,
                "file": None,
            }
            if not url:
                entry["note"] = "no url"
                summary["results"].append(entry)
                continue

            params: dict[str, str] = {"api_key": api_key, "url": url, "country_code": country}
            if render:
                params["render"] = "true"
            print(f"[bestsellers] {platform} ...", end=" ", flush=True)
            try:
                r = client.get("https://api.scraperapi.com/", params=params)
                entry["status"] = int(r.status_code)
                body = r.text or ""
                if r.status_code == 200 and "Protected domains may require" not in body:
                    ext = _extract_bestseller_snippet(body, max_chars=max_chars)
                    entry["names"] = len(ext["name_candidates"])
                    entry["ratings"] = len(ext["ratings"])
                    entry["ok"] = bool(ext["name_candidates"] or ext["ratings"])
                    fpath = out / f"{key}.txt"
                    lines = [
                        f"PLATFORM: {platform}",
                        f"URL: {url}",
                        f"STATUS: {r.status_code}",
                        "NAME_CANDIDATES:",
                        *[f"  - {n}" for n in ext["name_candidates"]],
                        f"RATINGS: {', '.join(ext['ratings'])}",
                        f"PRICES: {', '.join(ext['prices'])}",
                        "TEXT_WINDOW:",
                        ext["text_window"],
                    ]
                    fpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    entry["file"] = str(fpath)
                    print(
                        f"OK ({r.status_code}, names={entry['names']}, ratings={entry['ratings']})",
                        flush=True,
                    )
                elif "Protected domains may require" in body or r.status_code in (403, 500):
                    entry["note"] = "protected-domain / 当前代理套餐不可达（需付费 premium 代理）"
                    print(f"BLOCKED ({r.status_code}, premium required)", flush=True)
                else:
                    entry["note"] = f"unexpected status {r.status_code}"
                    print(f"FAIL ({r.status_code})", flush=True)
            except Exception as exc:  # noqa: BLE001
                entry["note"] = f"error: {str(exc)[:120]}"
                print(f"ERROR ({str(exc)[:60]})", flush=True)
            summary["results"].append(entry)
            time.sleep(0.2)

    ok_n = sum(1 for e in summary["results"] if e.get("ok"))
    summary["ok_count"] = ok_n
    summary["target_count"] = len(targets)
    (out / "_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"[bestsellers] done: {ok_n}/{len(targets)} sites yielded data.", flush=True
    )
    return summary


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


def overseas_load_articles_from_disk(
    *,
    signals_dir: str,
    source_list_path: str = "input/api/source_list.json",
    max_items_per_source: int = 25,
    time_window_hours: int = 48,
) -> dict[str, Any]:
    src_payload = overseas_read_source_list(source_list_path)
    sources = src_payload.get("sources")
    if not isinstance(sources, list):
        sources = []

    sig_dir = Path(signals_dir)
    now = _utc_now()
    cutoff = now - timedelta(hours=float(time_window_hours or 48))

    out_sources: list[dict[str, Any]] = []
    items: list[ArticleItem] = []

    for s in sources:
        if not isinstance(s, dict):
            continue

        # research-only sources have no baseline payload on disk.
        if str(s.get("fetchable") or "rss").strip().lower() == "research-only":
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

        category = _normalize_category(s.get("category"))
        markets = _normalize_markets(s.get("markets"))
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
                    category=category,
                    markets=markets,
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
                "category": category,
                "markets": markets,
                "tracks": tracks,
            }
        )

    # Compute comparable deterministic score for sorting.
    def _item_score(it: ArticleItem) -> float:
        w = _signal_weight(it.signal_level)
        rec = 0.0
        if it.published_ts:
            # 0..window -> 20..0 (linear decay)
            age_h = max(0.0, (now.timestamp() - it.published_ts) / 3600.0)
            rec = max(
                0.0,
                20.0
                * (
                    1.0
                    - min(age_h, float(time_window_hours or 48))
                    / float(time_window_hours or 48)
                ),
            )
        return float(w) + rec

    items.sort(key=_item_score, reverse=True)

    return {
        "window": {
            "time_window_hours": int(time_window_hours or 48),
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


def _read_text_file(path: str) -> str:
    """Read a UTF-8 text file. Used when the agent passes a *path* instead of
    inline JSON content — this keeps large payloads out of the model context and
    out of MCP tool string arguments (which the gh-aw gateway caps at 10 KB)."""
    return Path(path).read_text(encoding="utf-8")


def _write_json_file(path: str, obj: Any) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _write_text_files(text: str, paths: Iterable[str | None]) -> list[str]:
    written: list[str] = []
    for path in paths:
        if not path:
            continue
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        written.append(str(path))
    return written


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


def _categories_from_tracks(tracks: Iterable[Any]) -> list[str]:
    return sorted(
        {str(t) for t in tracks if isinstance(t, str) and t in _PRODUCT_CATEGORIES}
    )


def _markets_from_tracks(tracks: Iterable[Any]) -> list[str]:
    out: list[str] = []
    for t in tracks:
        if isinstance(t, str) and t.startswith("market:"):
            m = t.split(":", 1)[1]
            if m and m not in out:
                out.append(m)
    return sorted(out)


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
            rec = max(0.0, 10.0 * (1.0 - min(age_h, 48.0) / 48.0))
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
            # Only product-category overlap (not market) nudges the threshold,
            # to avoid over-merging unrelated items that merely share a market.
            cat_overlap = {t for t in tracks_set if t in _PRODUCT_CATEGORIES} & {
                t for t in c_tracks if t in _PRODUCT_CATEGORIES
            }
            if cat_overlap:
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

        all_tracks = [
            t for x in c_items for t in (x.get("tracks") or []) if isinstance(t, str)
        ]
        categories = _categories_from_tracks(all_tracks)
        markets = _markets_from_tracks(all_tracks)

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

        # Determine category (trend vs single).
        category = "trend" if coverage >= 2 or size >= 3 else "single"
        if signal_max >= 20 and coverage == 1 and size <= 2:
            category = "single"

        # should_chase: prioritize high signal and/or coverage.
        should_chase = (
            "yes" if (score >= 65.0 or signal_max >= 20 or coverage >= 3) else "no"
        )

        title = str(c_items[0].get("title") or "(untitled)") if c_items else "(empty)"
        summary_bits: list[str] = []
        if categories:
            summary_bits.append(
                "品类=" + ", ".join(_CATEGORY_LABELS.get(x, x) for x in categories)
            )
        if markets:
            summary_bits.append(
                "市场=" + ", ".join(_MARKET_LABELS.get(x, x) for x in markets)
            )
        if companies:
            summary_bits.append(f"品牌={', '.join(companies[:3])}")
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
                "categories": categories,
                "markets": markets,
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
    hotspots = hotspots[: max(1, int(top_k or 9))]
    return {"mode": "fallback", "top_k": int(top_k or 9), "hotspots": hotspots}


def overseas_cluster_or_fallback(
    *,
    raw_signals_json: str = "",
    clusters_json: str = "",
    top_k: int = 9,
    raw_signals_path: str | None = None,
    clusters_candidate_path: str | None = None,
    out_path: str | None = None,
) -> dict[str, Any]:
    # Prefer file paths when provided: keeps large JSON out of the model context
    # and out of MCP tool arguments (gh-aw gateway caps string args at 10 KB).
    if raw_signals_path:
        raw_signals_json = _read_text_file(raw_signals_path)
    if clusters_candidate_path:
        clusters_json = _read_text_file(clusters_candidate_path)
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
            categories = h.get("categories")
            if not isinstance(categories, list):
                cat_single = _normalize_category(h.get("category"))
                categories = [cat_single] if cat_single else []
            categories = [
                _normalize_category(c) or str(c)
                for c in categories
                if isinstance(c, str) and c
            ]
            markets = _normalize_markets(h.get("markets"))
            sanitized.append(
                {
                    "hotspot_id": str(h.get("hotspot_id") or f"H{idx:02d}"),
                    "title": title,
                    "summary": str(h.get("summary") or ""),
                    "category": str(h.get("category") or "trend"),
                    "categories": categories,
                    "markets": markets,
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
            if len(sanitized) >= int(top_k or 9):
                break
        result: dict[str, Any] = {
            "mode": "llm",
            "top_k": int(top_k or 9),
            "hotspots": sanitized,
        }
    else:
        result = _fallback_cluster(
            [x for x in items if isinstance(x, dict)], top_k=int(top_k or 9)
        )

    if out_path:
        _write_json_file(out_path, result)
    return result


def overseas_insight_or_fallback(
    *,
    clusters_json: str = "",
    insights_json: str = "",
    clusters_path: str | None = None,
    insights_candidate_path: str | None = None,
    out_path: str | None = None,
) -> dict[str, Any]:
    if clusters_path:
        clusters_json = _read_text_file(clusters_path)
    if insights_candidate_path:
        insights_json = _read_text_file(insights_candidate_path)

    # Try LLM insights.
    try:
        llm_obj = _extract_json(insights_json)
        if isinstance(llm_obj, list):
            llm_obj = {"insights": llm_obj}
        if isinstance(llm_obj, dict) and isinstance(llm_obj.get("insights"), list):
            result = {"mode": "llm", "insights": llm_obj.get("insights")}
            if out_path:
                _write_json_file(out_path, result)
            return result
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

        cats_val = h.get("categories")
        cats = [c for c in cats_val if isinstance(c, str)] if isinstance(cats_val, list) else []
        cat_label = "、".join(_CATEGORY_LABELS.get(c, c) for c in cats) if cats else "跨境电商"

        what_changed = "".join(
            [
                f"近期出现了与“{title}”相关的{cat_label}出海市场动态。",
                f"来源覆盖 {len(platforms)} 个渠道。" if platforms else "",
            ]
        ).strip()
        why = "趋势" if category == "trend" else "重要更新"
        why_it_matters = (
            f"这是一条出海市场{why}信号，可能影响选品方向、定价策略与营销节奏。"
        )
        who = ["选品与运营团队", "品牌方与市场团队", "供应链与采购"]
        if companies:
            who.append("关注相关品牌/竞品动态的团队")
        next_actions = [
            "查看引用链接确认原始信息与发布时间",
            "评估该信号对自身品类选品与定价的影响",
            "如为竞品爆品或新兴趋势，纳入竞品与选品分析",
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

    result = {"mode": "fallback", "insights": insights}
    if out_path:
        _write_json_file(out_path, result)
    return result


# 北美热销榜「销量代理」字段：用公开榜单排名 + 评分 + 评价数 + 趋势作为销量代理，
# 不含精确件数/GMV（免费抓取不可得，付费工具方有）。
_PRODUCT_PLATFORMS = {
    "amazon": "Amazon",
    "sephora": "Sephora",
    "ulta": "Ulta",
    "target": "Target",
    "tiktok": "TikTok Shop",
}


def _coerce_number(v: Any) -> Any:
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        if m:
            try:
                f = float(m.group())
                return int(f) if f.is_integer() else f
            except ValueError:
                return None
    return None


def overseas_products_or_fallback(
    *,
    products_json: str = "",
    products_candidate_path: str | None = None,
    out_path: str | None = None,
    top_n: int = 5,
) -> dict[str, Any]:
    """Validate + persist the「北美热销 TOP-N 产品」list (rank/rating/reviews/trend
    as sales proxies). Path-based + out_path, consistent with the other tools.
    Falls back to an empty list (with a note) when the candidate is unusable —
    we never fabricate sales numbers."""
    if products_candidate_path:
        products_json = _read_text_file(products_candidate_path)

    top_n = max(1, int(top_n or 5))
    try:
        obj = _extract_json(products_json)
        if isinstance(obj, list):
            obj = {"products": obj}
        if isinstance(obj, dict) and isinstance(obj.get("products"), list):
            sanitized: list[dict[str, Any]] = []
            for i, p in enumerate(obj["products"], start=1):
                if not isinstance(p, dict):
                    continue
                plat_raw = str(p.get("platform") or "").strip()
                plat_key = plat_raw.lower()
                platform = next(
                    (lbl for k, lbl in _PRODUCT_PLATFORMS.items() if k in plat_key),
                    plat_raw,
                )
                sanitized.append(
                    {
                        "rank": int(_coerce_number(p.get("rank")) or i),
                        "name": str(p.get("name") or p.get("title") or "").strip(),
                        "brand": str(p.get("brand") or "").strip(),
                        "subcategory": str(p.get("subcategory") or "").strip(),
                        "price": str(p.get("price") or p.get("price_band") or "").strip(),
                        "rating": _coerce_number(p.get("rating")),
                        "review_count": _coerce_number(p.get("review_count")),
                        "trend": str(p.get("trend") or "").strip(),
                        "platform": platform,
                        "url": str(p.get("url") or "").strip(),
                        "evidence": str(p.get("evidence") or p.get("data_source") or "").strip(),
                        "selling_points": [
                            str(x).strip()
                            for x in (p.get("selling_points") or [])
                            if isinstance(x, str) and x.strip()
                        ],
                        "why_hot": str(p.get("why_hot") or "").strip(),
                    }
                )
                if len(sanitized) >= top_n:
                    break
            if sanitized:
                result = {"mode": "llm", "top_n": top_n, "products": sanitized}
                if out_path:
                    _write_json_file(out_path, result)
                return result
    except Exception:
        pass

    result = {
        "mode": "fallback",
        "top_n": top_n,
        "products": [],
        "note": "未获取到可用的电商榜单数据（站点反爬/SPA 渲染），TOP产品改由 RSS 新闻信号兜底；请在报告中注明缺口。",
    }
    if out_path:
        _write_json_file(out_path, result)
    return result


def _render_products_section(products: list[dict[str, Any]]) -> list[str]:
    """Render the「北美热销 TOP 产品」markdown section (proxy metrics)."""
    lines: list[str] = ["## 北美热销 TOP 产品（榜单/评价代理）\n"]
    products = [p for p in products if isinstance(p, dict)]
    if not products:
        lines.append(
            "（本次未抓到可用的电商榜单数据，主流站点多为 SPA/反爬；本期热销以新闻信号中的热门品牌/产品兜底，详见上文热点话题。）\n"
        )
        return lines
    lines.append("> 口径说明：免费抓取无法获得精确销量（件数/GMV）。下表以**公开榜单排名 + 评分 + 评价数 + 趋势**作为销量代理。")
    lines.append("")
    lines.append("| 排名 | 产品 | 品牌 | 子类 | 价格带 | 评分 | 评价数 | 趋势 | 平台 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for p in sorted(products, key=lambda x: int(_coerce_number(x.get("rank")) or 999)):
        def _c(v: Any) -> str:
            return str(v).replace("|", "/") if v not in (None, "") else "—"

        lines.append(
            "| {rank} | {name} | {brand} | {sub} | {price} | {rating} | {rev} | {trend} | {plat} |".format(
                rank=_c(p.get("rank")),
                name=_c(p.get("name")),
                brand=_c(p.get("brand")),
                sub=_c(p.get("subcategory")),
                price=_c(p.get("price")),
                rating=_c(p.get("rating")),
                rev=_c(p.get("review_count")),
                trend=_c(p.get("trend")),
                plat=_c(p.get("platform")),
            )
        )
    lines.append("")
    # 卖点与来源链接
    for p in sorted(products, key=lambda x: int(_coerce_number(x.get("rank")) or 999)):
        name = str(p.get("name") or "").strip()
        if not name:
            continue
        why = str(p.get("why_hot") or "").strip()
        sps = "、".join(p.get("selling_points") or [])
        url = str(p.get("url") or "").strip()
        bits = []
        if why:
            bits.append(f"为什么火：{why}")
        if sps:
            bits.append(f"核心卖点：{sps}")
        detail = "；".join(bits)
        line = f"- **{name}**" + (f"（{detail}）" if detail else "")
        if url:
            line += f" {url}"
        lines.append(line)
    lines.append("")
    return lines


def overseas_render_report_or_fallback(
    *,
    clusters_json: str = "",
    insights_json: str = "",
    draft_markdown: str = "",
    clusters_path: str | None = None,
    insights_path: str | None = None,
    draft_path: str | None = None,
    products_json: str = "",
    products_path: str | None = None,
    out_path: str | None = None,
    frontend_out_path: str | None = None,
) -> str | dict[str, Any]:
    if clusters_path:
        clusters_json = _read_text_file(clusters_path)
    if insights_path:
        insights_json = _read_text_file(insights_path)
    if draft_path:
        draft_markdown = _read_text_file(draft_path)
    if products_path:
        try:
            products_json = _read_text_file(products_path)
        except OSError:
            products_json = ""

    products_list: list[dict[str, Any]] = []
    if products_json:
        try:
            pobj = _extract_json(products_json)
            if isinstance(pobj, dict):
                pobj = pobj.get("products")
            if isinstance(pobj, list):
                products_list = [p for p in pobj if isinstance(p, dict)]
        except Exception:
            products_list = []

    def _emit(final_md: str, mode: str) -> str | dict[str, Any]:
        written = _write_text_files(final_md, [out_path, frontend_out_path])
        if written:
            return {"mode": mode, "chars": len(final_md), "out_paths": written}
        return final_md

    md = (draft_markdown or "").strip()
    # If LLM produced a plausible markdown, keep it.
    if md and "(mock" not in md.lower() and len(md) > 120:
        return _emit(md.strip() + "\n", "llm")

    clusters = _extract_json(clusters_json)
    if isinstance(clusters, list):
        clusters = {"hotspots": clusters}
    hotspots = clusters.get("hotspots") if isinstance(clusters, dict) else None
    if not isinstance(hotspots, list):
        hotspots = []
    hotspots = [h for h in hotspots if isinstance(h, dict)]

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

    def _hs_categories(h: dict[str, Any]) -> list[str]:
        v = h.get("categories")
        out = [x for x in v if isinstance(x, str)] if isinstance(v, list) else []
        return [c for c in out if c in _PRODUCT_CATEGORIES]

    def _hs_markets(h: dict[str, Any]) -> list[str]:
        v = h.get("markets")
        return [x for x in v if isinstance(x, str)] if isinstance(v, list) else []

    def _render_hotspot(h: dict[str, Any]) -> str:
        hid = str(h.get("hotspot_id") or "")
        title = str(h.get("title") or "")
        score = str(h.get("overall_heat_score") or "")
        cats = _hs_categories(h)
        mkts = _hs_markets(h)
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
        if cats:
            lines.append(f"- 品类：{', '.join(_CATEGORY_LABELS.get(c, c) for c in cats)}")
        if mkts:
            lines.append(f"- 市场：{', '.join(_MARKET_LABELS.get(m, m) for m in mkts)}")
        if companies:
            lines.append(f"- 涉及品牌：{', '.join([str(x) for x in companies[:6]])}")
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

    # Group hotspots by product category.
    by_cat: dict[str, list[dict[str, Any]]] = {c: [] for c in _PRODUCT_CATEGORIES}
    uncategorized: list[dict[str, Any]] = []
    for h in hotspots:
        cats = _hs_categories(h)
        if not cats:
            uncategorized.append(h)
            continue
        for c in cats:
            by_cat.setdefault(c, []).append(h)

    # Group hotspots by market.
    by_market: dict[str, list[dict[str, Any]]] = {m: [] for m in _MARKET_LABELS}
    for h in hotspots:
        for m in _hs_markets(h):
            by_market.setdefault(m, []).append(h)

    lines: list[str] = []
    lines.append("# 出海市场洞察日报（兜底版）\n")
    lines.append(f"- 生成时间：{_to_iso(_utc_now())}")
    lines.append("- 品类：美妆护肤 / 3C电子 / 饰品配饰")
    lines.append("- 目标市场：北美 / 欧洲 / 东南亚 / 全球")
    lines.append("")

    # 今日摘要
    lines.append("## 今日摘要\n")
    cat_counts = "，".join(
        f"{_CATEGORY_LABELS[c]} {len(by_cat.get(c) or [])}" for c in _PRODUCT_CATEGORIES
    )
    lines.append(f"- 本期共 {len(hotspots)} 个热点（{cat_counts}）。")
    for h in hotspots[:3]:
        lines.append(f"- {h.get('hotspot_id')}：{h.get('title')}")
    lines.append("")

    # 热点话题（分品类）
    lines.append("## 热点话题（分品类）\n")
    any_cat = False
    for c in _PRODUCT_CATEGORIES:
        hs = by_cat.get(c) or []
        if not hs:
            continue
        any_cat = True
        lines.append(f"### {_CATEGORY_LABELS[c]}\n")
        for h in sorted(
            hs, key=lambda x: int(x.get("overall_heat_score") or 0), reverse=True
        ):
            lines.append(_render_hotspot(h))
    if uncategorized:
        any_cat = True
        lines.append("### 综合 / 未分类\n")
        for h in uncategorized:
            lines.append(_render_hotspot(h))
    if not any_cat:
        lines.append("（未提取到可分类的热点）\n")

    # 热门产品 / 潜力爆品
    lines.append("## 热门产品 / 潜力爆品\n")
    if hotspots:
        lines.append("| 主题/产品 | 品类 | 市场 | 热度 | 来源 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for h in hotspots:
            cats = _hs_categories(h)
            mkts = _hs_markets(h)
            cov_val = h.get("coverage")
            cov = cov_val if isinstance(cov_val, dict) else {}
            platforms_val = cov.get("platforms")
            platforms = platforms_val if isinstance(platforms_val, list) else []
            cat_s = "/".join(_CATEGORY_LABELS.get(c, c) for c in cats) or "—"
            mkt_s = "/".join(_MARKET_LABELS.get(m, m) for m in mkts) or "—"
            src_s = ", ".join(str(p) for p in platforms[:3]) or "—"
            title = str(h.get("title") or "").replace("|", "/")
            lines.append(
                f"| {title} | {cat_s} | {mkt_s} | {h.get('overall_heat_score')} | {src_s} |"
            )
        lines.append("")
        lines.append("> 注：兜底版未结构化提取价格带与核心卖点，请在启用 LLM 的运行中补全。")
        lines.append("")
    else:
        lines.append("（未提取到产品信号）\n")

    # 北美热销 TOP 产品（榜单/评价代理）
    lines.extend(_render_products_section(products_list))

    # 分市场速览
    lines.append("## 分市场速览\n")
    any_market = False
    for m in ("na", "eu", "sea", "global"):
        hs = by_market.get(m) or []
        if not hs:
            continue
        any_market = True
        lines.append(f"### {_MARKET_LABELS[m]}\n")
        for h in sorted(
            hs, key=lambda x: int(x.get("overall_heat_score") or 0), reverse=True
        )[:6]:
            lines.append(f"- {h.get('hotspot_id')}：{h.get('title')}")
        lines.append("")
    if not any_market:
        lines.append("（未提取到带市场标签的热点）\n")

    # 选品与营销行动建议
    lines.append("## 选品与营销行动建议\n")
    lines.append("（兜底版未生成；请在启用 LLM 的工作流运行中产出结构化选品与营销建议。）\n")

    # 风险与合规提示
    lines.append("## 风险与合规提示\n")
    lines.append("- 关税与税务：关注目标市场进口关税、VAT/GST 与合规申报要求。")
    lines.append(
        "- 产品认证：美妆需符合 FDA / EU CPNP，3C 需 FCC / CE / RoHS，饰品需重金属与镍释放限值。"
    )
    lines.append("- 平台政策：留意 Amazon / TikTok Shop / Temu 等类目准入与广告政策变化。")
    lines.append("- 知识产权：核查商标与外观专利，规避侵权下架风险。")
    lines.append("- 物流履约：评估时效、退货率与海外仓布局。")
    lines.append("")

    # 数据来源
    lines.append("## 数据来源\n")
    seen_urls: set[str] = set()
    src_lines: list[str] = []
    for h in hotspots:
        samples_val = h.get("samples")
        samples = samples_val if isinstance(samples_val, list) else []
        for s in samples:
            if not isinstance(s, dict):
                continue
            u = str(s.get("url") or "").strip()
            if not u or u in seen_urls:
                continue
            seen_urls.add(u)
            t = str(s.get("title") or "").strip()
            src_lines.append(f"- {t} ({u})" if t else f"- {u}")
            if len(src_lines) >= 20:
                break
        if len(src_lines) >= 20:
            break
    if src_lines:
        lines.extend(src_lines)
    else:
        lines.append("（无可引用来源）")
    lines.append("")

    lines.append("---\n")
    lines.append("说明：本报告在无 LLM 或 LLM 输出不可解析时，由确定性兜底逻辑生成。\n")
    return _emit("\n".join(lines).strip() + "\n", "fallback")


def register_tools(registry: object) -> None:
    register = getattr(registry, "register_tool", None)
    if not callable(register):
        return

    register("overseas.read_source_list", overseas_read_source_list)
    register("overseas.fetch_all_to_disk", overseas_fetch_all_to_disk)
    register("overseas.load_articles_from_disk", overseas_load_articles_from_disk)
    register("overseas.cluster_or_fallback", overseas_cluster_or_fallback)
    register("overseas.insight_or_fallback", overseas_insight_or_fallback)
    register("overseas.products_or_fallback", overseas_products_or_fallback)
    register("overseas.render_report_or_fallback", overseas_render_report_or_fallback)
