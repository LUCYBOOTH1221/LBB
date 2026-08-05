#!/usr/bin/env python3
"""
Pull assignments and events from the Canvas iCal feed into data/canvas.json.

Set CANVAS_ICS_URL in .env (gitignored) -- see docs/canvas-and-groupme.md.
Uses only the standard library; no ics parser dependency.

Usage:
    python3 scripts/fetch_canvas.py
    python3 scripts/fetch_canvas.py --file sample.ics   # parse a local file
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "canvas.json"
ENV = ROOT / ".env"


def load_env() -> None:
    """Minimal .env reader so there's no python-dotenv dependency."""
    if not ENV.exists():
        return
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def unfold(raw: str) -> list[str]:
    """RFC 5545 folds long lines with a leading space/tab on continuations."""
    out: list[str] = []
    for line in raw.splitlines():
        if line[:1] in (" ", "\t") and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def unescape(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def parse_dt(value: str) -> str | None:
    """Canvas emits DTSTART as YYYYMMDD or YYYYMMDDTHHMMSSZ. Return ISO-8601."""
    value = value.strip()
    for fmt, has_time in (("%Y%m%dT%H%M%SZ", True), ("%Y%m%dT%H%M%S", True), ("%Y%m%d", False)):
        try:
            dt = datetime.strptime(value, fmt)
            if has_time:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            continue
    return None


def parse_ics(raw: str) -> list[dict]:
    events: list[dict] = []
    current: dict | None = None

    for line in unfold(raw):
        if line.startswith("BEGIN:VEVENT"):
            current = {}
            continue
        if line.startswith("END:VEVENT"):
            if current:
                events.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue

        name, _, value = line.partition(":")
        prop = name.split(";", 1)[0].upper()

        if prop == "SUMMARY":
            current["title"] = unescape(value)
        elif prop in ("DTSTART", "DUE"):
            current["due"] = parse_dt(value)
        elif prop == "CATEGORIES":
            current["course"] = unescape(value)
        elif prop == "URL":
            current["url"] = value
        elif prop == "UID":
            current["uid"] = value
        elif prop == "DESCRIPTION":
            text = unescape(value).strip()
            if text:
                current["description"] = text[:500]

    return [e for e in events if e.get("title") and e.get("due")]


def tag_for(course: str | None, classes: list[dict]) -> str | None:
    """Match a Canvas course name against config.yaml `classes:` entries."""
    if not course:
        return None
    haystack = course.lower()
    for cls in classes:
        tag, name = cls.get("tag"), cls.get("name")
        if tag and tag.lower().replace("-", "") in haystack.replace("-", "").replace(" ", ""):
            return tag
        if name and name.lower() in haystack:
            return tag
    return None


def load_classes() -> list[dict]:
    try:
        import yaml
    except ImportError:
        return []
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8")) or {}
    return cfg.get("classes") or []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="parse a local .ics instead of fetching")
    args = ap.parse_args()

    if args.file:
        raw = Path(args.file).read_text(encoding="utf-8")
    else:
        load_env()
        url = os.environ.get("CANVAS_ICS_URL")
        if not url:
            sys.exit(
                "CANVAS_ICS_URL is not set.\n"
                "Canvas > Calendar > Calendar Feed, then:\n"
                "  echo 'CANVAS_ICS_URL=https://...' >> .env\n"
                "See docs/canvas-and-groupme.md"
            )
        with urllib.request.urlopen(url, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")

    events = parse_ics(raw)
    classes = load_classes()
    for ev in events:
        ev["tag"] = tag_for(ev.get("course"), classes)

    events.sort(key=lambda e: e["due"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "count": len(events),
                "events": events,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    untagged = sum(1 for e in events if not e.get("tag"))
    print(f"Parsed {len(events)} events -> {OUT.relative_to(ROOT)}")
    if events:
        print(f"Earliest: {events[0]['due'][:10]}   Latest: {events[-1]['due'][:10]}")
    if untagged and classes:
        print(f"Note: {untagged} events matched no class tag; check `classes:` in config.yaml")
    elif not classes:
        print("Note: `classes:` in config.yaml is empty, so nothing was tagged.")


if __name__ == "__main__":
    main()
