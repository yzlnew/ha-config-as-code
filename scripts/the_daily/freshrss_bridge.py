"""Fetch + filter top FreshRSS items via the existing /root/wiki pipeline.
Returns dashboard-ready dicts. Any error → []."""

from __future__ import annotations

import os as _os
import re
import sys
import sys as _sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = _os.path.dirname(_os.path.abspath(__file__))
_SCRIPTS = _os.path.dirname(_HERE)
for _p in (_HERE, _SCRIPTS):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import _bootstrap  # noqa: F401

WIKI_SCRIPTS = Path("/root/wiki/scripts")


def _src_label(source: str) -> str:
    """Short uppercase tag (~3-5 chars) from a feed source name."""
    if not source:
        return "•"
    s = source.strip()
    # Common short forms — keep mockup feel
    short_map = {
        "Hacker News": "HN",
        "The Verge": "VRG",
        "Financial Times": "FT",
        "Ars Technica": "ARS",
        "Reuters": "RTR",
        "Bloomberg": "BBG",
        "The New York Times": "NYT",
        "Wired": "WRD",
        "界面新闻": "界面",
        "少数派": "少数派",
    }
    for k, v in short_map.items():
        if k in s:
            return v
    # Fallback: first uppercase letters / first word truncated
    upper = re.sub(r"[^A-Z]", "", s)
    if 2 <= len(upper) <= 5:
        return upper
    word = re.split(r"[\s|·:\-]", s, maxsplit=1)[0]
    return word[:5].upper() if word.isascii() else word[:2]


def _human_ago(when: datetime) -> str:
    now = datetime.now(timezone.utc)
    delta = now - (when.astimezone(timezone.utc) if when.tzinfo else when.replace(tzinfo=timezone.utc))
    sec = max(0, int(delta.total_seconds()))
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m"
    if sec < 86400:
        return f"{sec // 3600}h"
    return f"{sec // 86400}d"


def fetch_top(limit: int = 6, pad: bool = False) -> tuple[list[dict], int]:
    """Return (items, total_unread). items is dashboard-ready; on any failure: ([], 0).

    pad=True tops the list up to `limit` with the most-recent remaining items when
    the scorer accepted fewer than `limit` (for the e-ink dashboard, which wants the
    column filled rather than the digest's strict relevance cut). Default off.
    """
    try:
        sys.path.insert(0, str(WIKI_SCRIPTS))
        import update_freshrss as uf  # type: ignore

        # Load /root/wiki/.env.freshrss.local (DEFAULT_ENV_FILE in script)
        uf.load_env_file(uf.DEFAULT_ENV_FILE)

        api_base = uf.freshrss_api_base(uf.env("FRESHRSS_BASE_URL"))
        auth = uf.client_login(
            api_base,
            uf.env("FRESHRSS_USERNAME"),
            uf.env("FRESHRSS_API_PASSWORD"),
        )
        items = uf.fetch_recent_items(api_base, auth, limit=50)
        total = len(items)
        scored = [(it, uf.score_item(it)) for it in items]
        kept = [
            (it, res)
            for it, res in scored
            if res.decision in ("accept", "maybe")
        ]
        kept.sort(
            key=lambda p: (
                p[1].decision != "accept",
                -p[1].score,
                -p[0].published.timestamp(),
            )
        )
        def _row(it):
            return {
                "src": _src_label(it.source),
                "title": it.title,
                "small": uf.summary_snippet(it.summary_html, 110),
                "ago": _human_ago(it.published),
                "url": it.url,
            }

        out: list[dict] = [_row(it) for it, _res in kept[:limit]]
        if pad and len(out) < limit:
            have = {d["url"] for d in out}
            for it in sorted(items, key=lambda i: -i.published.timestamp()):
                if len(out) >= limit:
                    break
                if it.url in have:
                    continue
                out.append(_row(it))
                have.add(it.url)
        return out, total
    except BaseException as exc:  # network, auth, missing env, SystemExit from imported script — degrade quietly
        if isinstance(exc, KeyboardInterrupt):
            raise
        print(f"[freshrss] {type(exc).__name__}: {exc}", file=sys.stderr)
        return [], 0
