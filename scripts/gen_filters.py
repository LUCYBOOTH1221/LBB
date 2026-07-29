#!/usr/bin/env python3
"""
Generate an importable Gmail filter file from config.yaml.

Gmail accepts filters as an Atom XML feed:
    Settings > Filters and Blocked Addresses > Import filters

Usage:
    python3 scripts/gen_filters.py            # writes mail/filters.xml
    python3 scripts/gen_filters.py --check    # print a summary, write nothing
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.yaml"
OUT = ROOT / "mail" / "filters.xml"

# Gmail rejects a filter whose query is too long. Splitting each sender group
# into chunks keeps every generated query comfortably under the limit.
SENDERS_PER_FILTER = 20


def load_config() -> dict:
    try:
        import yaml
    except ImportError:
        sys.exit("PyYAML is required:  pip install pyyaml")
    with CONFIG.open() as fh:
        return yaml.safe_load(fh)


def entry(properties: dict[str, str]) -> str:
    """Render one <entry> block. Gmail ignores properties it doesn't know."""
    lines = [
        "  <entry>",
        "    <category term='filter'></category>",
        "    <title>Mail Filter</title>",
    ]
    extra = {"'": "&apos;", '"': "&quot;"}
    for name, value in properties.items():
        safe = escape(str(value), extra)
        lines.append(f"    <apps:property name='{name}' value='{safe}'/>")
    lines.append("  </entry>")
    return "\n".join(lines)


def chunked(items: list[str], size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def from_query(senders: list[str]) -> str:
    """Gmail's `from:` accepts an OR-joined brace group."""
    return "{" + " ".join(senders) + "}"


def build(config: dict) -> tuple[str, list[str]]:
    noise = config.get("noise") or {}
    people = config.get("people") or []
    summary: list[str] = []
    entries: list[str] = []

    # -- 1. VIPs first -------------------------------------------------------
    # Gmail applies every matching filter, so this cannot be undone by a later
    # rule -- but nothing below targets these addresses anyway.
    vips = [p["address"] for p in people if p.get("address") and p.get("priority") == "high"]
    domains = config.get("never_filter_domains") or []
    protected = vips + [f"*@{d}" for d in domains]
    if protected:
        entries.append(
            entry(
                {
                    "from": from_query(protected),
                    "shouldAlwaysMarkAsImportant": "true",
                    "shouldNeverSpam": "true",
                }
            )
        )
        summary.append(f"1 protect rule covering {len(protected)} VIP senders/domains")

    # -- 2. Noise groups -----------------------------------------------------
    # archive + label, never mark read: archiving clears the inbox while the
    # unread badge on the label still tells you something arrived.
    groups = [
        ("transaction_alerts", "Receipts/Transactions", True, True),
        ("duplicate_receipts", "Receipts/Transactions", True, True),
        ("retail", "Shopping & Promos", True, True),
        ("newsletters", "Newsletters & News", True, False),
        ("job_alerts", "Internships & Career", True, False),
        ("transactional", "Receipts/Transactions", True, True),
    ]

    for key, label, archive, mark_read in groups:
        senders = noise.get(key) or []
        if not senders:
            continue
        for chunk in chunked(senders, SENDERS_PER_FILTER):
            props = {"from": from_query(chunk), "label": label}
            if archive:
                props["shouldArchive"] = "true"
            if mark_read:
                props["shouldMarkAsRead"] = "true"
            props["shouldNeverMarkAsImportant"] = "true"
            entries.append(entry(props))
        n = -(-len(senders) // SENDERS_PER_FILTER)
        summary.append(f"{n} filter(s) -> {label:<24} ({len(senders)} senders, {key})")

    feed = (
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<feed xmlns='http://www.w3.org/2005/Atom' "
        "xmlns:apps='http://schemas.google.com/apps/2006'>\n"
        "  <title>LBB mail filters</title>\n"
        + "\n".join(entries)
        + "\n</feed>\n"
    )
    return feed, summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="summarize without writing")
    args = ap.parse_args()

    feed, summary = build(load_config())

    print("Filter plan:")
    for line in summary:
        print(f"  {line}")
    print(f"\nTotal <entry> blocks: {feed.count('<entry>')}")

    if args.check:
        print("\n--check: nothing written.")
        return

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(feed)
    print(f"\nWrote {OUT.relative_to(ROOT)}")
    print("Import at: Gmail > Settings > Filters and Blocked Addresses > Import filters")


if __name__ == "__main__":
    main()
