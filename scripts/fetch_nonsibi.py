#!/usr/bin/env python3
"""
Pull the Non Sibi content calendar from Supabase into data/content-calendar.json.

The Google Sheet is the source of truth; AllInOne.gs syncs it to Supabase on
every edit plus a 15-minute backstop. This reads that replica -- it never
writes, so it cannot corrupt the sheet.

Key handling:
    SUPABASE_ANON_KEY      preferred. Publishable, RLS-constrained.
    SUPABASE_SERVICE_KEY   fallback. Full access, bypasses RLS -- fine here
                           because this runs on your machine, but it must never
                           reach a browser.

Put whichever you use in .env (gitignored):
    echo 'SUPABASE_ANON_KEY=eyJ...' >> .env

Usage:
    python3 scripts/fetch_nonsibi.py
    python3 scripts/fetch_nonsibi.py --weeks 6
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "content-calendar.json"
ENV = ROOT / ".env"


def load_env() -> None:
    if not ENV.exists():
        return
    for line in ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def config() -> dict:
    import yaml

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text()) or {}
    supa = (cfg.get("integrations") or {}).get("supabase") or {}
    if not supa.get("url"):
        sys.exit("integrations.supabase.url is not set in config.yaml")
    return supa


def pick_key() -> tuple[str, str]:
    anon = os.environ.get("SUPABASE_ANON_KEY")
    if anon:
        return anon, "anon"
    service = os.environ.get("SUPABASE_SERVICE_KEY")
    if service:
        print("  note: using SUPABASE_SERVICE_KEY. It bypasses RLS -- keep it out of any browser.")
        return service, "service_role"
    sys.exit(
        "No Supabase key found.\n"
        "Add one to .env (gitignored):\n"
        "  echo 'SUPABASE_ANON_KEY=eyJ...' >> .env\n"
        "Supabase > Project Settings > API. Prefer the anon/publishable key."
    )


# The `calendar` table columns, as written by readCalendarRows_() in AllInOne.gs.
FIELDS = [
    "id", "sort_date", "target_go_live", "publish_date", "week_of",
    "posting_from", "theme", "topic", "working_title", "cta", "channel",
    "status", "link", "repost_to", "notes",
]


def is_live(row: dict) -> bool:
    """Mirrors isLive_() in AllInOne.gs: a real LinkedIn link AND Live status."""
    return "linkedin.com" in (row.get("link") or "").lower() and "live" in (row.get("status") or "").lower()


def fetch(supa: dict, key: str, since: str, until: str) -> list[dict]:
    query = urllib.parse.urlencode(
        {
            "select": ",".join(FIELDS),
            "sort_date": f"gte.{since}",
            "and": f"(sort_date.lte.{until})",
            "order": "sort_date.asc",
        }
    )
    url = f"{supa['url'].rstrip('/')}/rest/v1/{supa.get('table', 'calendar')}?{query}"
    req = urllib.request.Request(
        url, headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:400]
        if exc.code in (401, 403):
            sys.exit(
                f"Supabase rejected the key ({exc.code}).\n{body}\n\n"
                "If using the anon key, the calendar table needs an RLS policy "
                "allowing select. Without one, anon reads return empty or 401."
            )
        sys.exit(f"Supabase error {exc.code}: {body}")
    except urllib.error.URLError as exc:
        sys.exit(f"Could not reach Supabase: {exc.reason}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, default=8, help="how far ahead to pull (default 8)")
    ap.add_argument("--back", type=int, default=2, help="weeks of history to keep (default 2)")
    args = ap.parse_args()

    load_env()
    supa = config()
    key, kind = pick_key()

    today = date.today()
    since = (today - timedelta(weeks=args.back)).isoformat()
    until = (today + timedelta(weeks=args.weeks)).isoformat()

    rows = fetch(supa, key, since, until)

    items = []
    for r in rows:
        when = r.get("publish_date") or r.get("target_go_live") or r.get("sort_date")
        if not when:
            continue
        items.append(
            {
                "id": f"nonsibi:{r.get('id')}",
                "date": when[:10],
                "title": r.get("working_title") or r.get("topic") or "(untitled)",
                "channel": r.get("channel") or "LinkedIn",
                "status": r.get("status") or "Not started",
                "owner": r.get("posting_from") or "",
                "theme": r.get("theme") or "",
                "link": r.get("link") or "",
                "notes": r.get("notes") or "",
                "live": is_live(r),
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "key_kind": kind,
                "window": {"from": since, "to": until},
                "count": len(items),
                "items": items,
            },
            indent=2,
        )
    )

    pending = sum(1 for i in items if not i["live"])
    print(f"Pulled {len(items)} rows -> {OUT.relative_to(ROOT)}")
    if items:
        print(f"  window {since} .. {until}")
        print(f"  {pending} not yet live, {len(items) - pending} live")
    else:
        print("  nothing in this window. Widen it with --weeks, or check the sheet.")


if __name__ == "__main__":
    main()
