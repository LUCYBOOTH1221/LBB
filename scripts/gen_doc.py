#!/usr/bin/env python3
"""
Create a document from a template and register it on the dashboard.

Filenames follow YYYY-MM-DD-<class-tag>-<slug>.md so they sort chronologically
and group by class in a plain directory listing.

Usage:
    python3 scripts/gen_doc.py reading-response "Arendt on judgment" --class POLS-4010
    python3 scripts/gen_doc.py meeting-notes "Check-in with Betsy" --with "Betsy Biern" --org "Make-A-Wish"
    python3 scripts/gen_doc.py --list
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "docs" / "templates"
OUTDIR = ROOT / "docs" / "generated"
INDEX = ROOT / "data" / "docs.json"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "untitled"


def available() -> list[str]:
    if not TEMPLATES.exists():
        return []
    return sorted(p.stem for p in TEMPLATES.glob("*.md"))


def render(body: str, values: dict[str, str]) -> str:
    """Fill {{KEY}} placeholders, then resolve {{#KEY}}...{{/KEY}} sections.

    A section survives only if its key has a non-empty value -- this is what
    lets `· {{ORG}}` disappear cleanly when no org was given, instead of
    leaving a dangling separator.
    """
    for key, value in values.items():
        pattern = r"\{\{#" + re.escape(key) + r"\}\}(.*?)\{\{/" + re.escape(key) + r"\}\}"
        body = re.sub(pattern, (r"\1" if value else ""), body, flags=re.DOTALL)
    # Any section whose key was never supplied is dropped.
    body = re.sub(r"\{\{#\w+\}\}.*?\{\{/\w+\}\}", "", body, flags=re.DOTALL)
    for key, value in values.items():
        body = body.replace("{{" + key + "}}", value)
    return body


def register(path: Path, title: str, tag: str, when: str) -> None:
    index = {"items": []}
    if INDEX.exists():
        try:
            index = json.loads(INDEX.read_text())
        except json.JSONDecodeError:
            pass
    rel = path.relative_to(ROOT).as_posix()
    items = [i for i in index.get("items", []) if i.get("path") != rel]
    items.insert(
        0,
        {
            "title": title,
            "tag": tag,
            "date": when,
            "path": rel,
            # dashboard/index.html sits one level down, so links step back up
            "url": f"../{rel}",
        },
    )
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps({"items": items}, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("template", nargs="?", help="template name (see --list)")
    ap.add_argument("title", nargs="?", help="document title")
    ap.add_argument("--class", dest="klass", default="", help="class tag, e.g. POLS-4010")
    ap.add_argument("--due", default="", help="due date, YYYY-MM-DD")
    ap.add_argument("--with", dest="attendees", default="", help="meeting attendees")
    ap.add_argument("--org", default="", help="organization")
    ap.add_argument("--source", default="", help="Gmail thread id / Canvas UID / Drive id")
    ap.add_argument("--list", action="store_true", help="list templates and exit")
    args = ap.parse_args()

    if args.list or not args.template:
        names = available()
        print("Templates:" if names else f"No templates found in {TEMPLATES}")
        for n in names:
            print(f"  {n}")
        sys.exit(0 if args.list else 1)

    src = TEMPLATES / f"{args.template}.md"
    if not src.exists():
        sys.exit(f"No template '{args.template}'. Available: {', '.join(available()) or 'none'}")
    if not args.title:
        sys.exit("A title is required.")

    today = date.today().isoformat()
    values = {
        "TITLE": args.title,
        "CLASS_TAG": args.klass,
        "DATE": today,
        "DUE": args.due,
        "ATTENDEES": args.attendees,
        "ORG": args.org,
        "SOURCE": args.source,
    }

    parts = [today] + ([args.klass] if args.klass else []) + [slugify(args.title)]
    out = OUTDIR / ("-".join(parts) + ".md")
    if out.exists():
        sys.exit(f"{out.relative_to(ROOT)} already exists; pick another title or delete it.")

    OUTDIR.mkdir(parents=True, exist_ok=True)
    out.write_text(render(src.read_text(), values))
    register(out, args.title, args.klass, today)

    print(f"Created {out.relative_to(ROOT)}")
    print("Rebuild the dashboard to see it:  python3 scripts/build_dashboard.py")


if __name__ == "__main__":
    main()
