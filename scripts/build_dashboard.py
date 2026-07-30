#!/usr/bin/env python3
"""
Render dashboard/index.html from config.yaml + data/*.json.

The page is divided into the workspaces defined in config.yaml -- Tulane,
Claude, Non Sibi, Personal -- each with its own accent, quick links, mail lane,
and panels. Mail routes into a workspace by sender domain (`match`), falling
through to whichever workspace is marked `default: true`.

Sources that aren't connected render as visibly inactive rather than being
hidden or filled with placeholder rows: the dashboard should never imply it
knows something it doesn't.

Usage:
    python3 scripts/build_dashboard.py
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "dashboard" / "index.html"

GMAIL_THREAD = "https://mail.google.com/mail/u/0/#inbox/"


def read_json(name: str) -> dict:
    path = DATA / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        print(f"  warning: {name} is not valid JSON ({exc}); treating as empty")
        return {}


def read_config() -> dict:
    import yaml

    return yaml.safe_load((ROOT / "config.yaml").read_text()) or {}


def e(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def ago(iso: str) -> str:
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return ""
    delta = datetime.now(timezone.utc) - then
    days, hours = delta.days, delta.seconds // 3600
    if days > 365:
        return f"{days // 365}y ago"
    if days > 30:
        return f"{days // 30}mo ago"
    if days > 0:
        return f"{days}d ago"
    if hours > 0:
        return f"{hours}h ago"
    return "just now"


def until(iso: str) -> tuple[str, str]:
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return "", "calm"
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    days = (then - datetime.now(timezone.utc)).days
    if days < 0:
        return f"{abs(days)}d overdue", "critical"
    if days == 0:
        return "due today", "critical"
    if days == 1:
        return "due tomorrow", "warn"
    if days <= 7:
        return f"in {days}d", "warn"
    return f"in {days}d", "calm"


def route(item: dict, spaces: list[dict], fallback: str) -> str:
    """Pick a workspace for a message.

    Order matters: an explicit `workspace` on the item wins, then an exact
    address match, then a domain match. Address-before-domain is what lets
    kberthelsen@tulane.edu belong to Claude even though the Tulane workspace
    claims all of tulane.edu -- otherwise workspace order would decide it.
    """
    if item.get("workspace"):
        return item["workspace"]
    sender = (item.get("from") or "").lower()
    if not sender:
        return fallback

    for space in spaces:
        for rule in space.get("match") or []:
            if "@" in rule and rule.lower() in sender:
                return space["id"]
    for space in spaces:
        for rule in space.get("match") or []:
            if "@" not in rule and rule.lower() in sender:
                return space["id"]
    return fallback


# --------------------------------------------------------------------------
# fragments
# --------------------------------------------------------------------------
def empty(message: str, hint: str = "") -> str:
    hint_html = f'<p class="empty-hint">{e(hint)}</p>' if hint else ""
    return f'<div class="empty"><p>{e(message)}</p>{hint_html}</div>'


def links_bar(links: list[dict]) -> str:
    if not links:
        return ""
    out = []
    for link in links:
        label = link.get("label")
        if not label:
            continue
        if not link.get("url"):
            # Known-missing link: shown, disabled, so it reads as a to-do
            # rather than silently vanishing from the row.
            out.append(f'<span class="qlink is-todo" title="URL not set yet">{e(label)}</span>')
            continue
        mark = ' <span class="q-confirm" title="unverified URL">?</span>' if link.get("confirm") else ""
        out.append(
            f'<a class="qlink" href="{e(link["url"])}" target="_blank" rel="noopener">{e(label)}{mark}</a>'
        )
    return f'<div class="qlinks">{"".join(out)}</div>' if out else ""


def compose_url(item: dict) -> str:
    """Gmail compose, prefilled as a reply to this sender.

    Gmail has no public deep link that opens a reply *inside* an existing
    thread, so this opens a fresh compose with Re: and the recipient filled
    in. For a genuine threaded draft, ask the agent -- it writes through the
    Gmail API and the draft appears attached to the real thread.
    """
    subject = item.get("subject") or ""
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    params = urlencode(
        {"view": "cm", "fs": "1", "to": item.get("from") or "", "su": subject},
        quote_via=quote,
    )
    return f"https://mail.google.com/mail/?{params}"


def mail_rows(items: list[dict]) -> str:
    """Each row carries Seen / Replied toggles plus a Draft action."""
    if not items:
        return empty("Nothing waiting here.")
    out = []
    for it in items:
        tid = e(it.get("id", ""))
        unread = " is-unread" if it.get("unread") else ""
        org = f'<span class="org">{e(it["org"])}</span>' if it.get("org") else ""
        why = f'<p class="row-why">{e(it["reason"])}</p>' if it.get("reason") else ""

        # A draft the agent already created wins over opening a blank compose.
        if it.get("draft_id"):
            draft = (
                f'<a class="act act-draft has-draft" target="_blank" rel="noopener" '
                f'href="https://mail.google.com/mail/u/0/#drafts/{e(it["draft_id"])}">Draft ready</a>'
            )
        else:
            draft = (
                f'<a class="act act-draft" target="_blank" rel="noopener" '
                f'href="{e(compose_url(it))}" data-act="draft">Draft</a>'
            )

        out.append(
            f"""<li class="row{unread}" data-id="{tid}">
  <div class="row-main">
    <div class="row-who"><span class="who">{e(it.get('name') or it.get('from'))}</span>{org}</div>
    <a class="row-subject" href="{GMAIL_THREAD}{tid}" target="_blank" rel="noopener">{e(it.get('subject') or '(no subject)')}</a>
    {why}
  </div>
  <div class="row-side">
    <time>{e(ago(it.get('received', '')))}</time>
    <div class="acts">
      <button type="button" class="act act-seen" data-act="seen" aria-pressed="false">Seen</button>
      {draft}
      <button type="button" class="act act-replied" data-act="replied" aria-pressed="false">Replied</button>
    </div>
  </div>
</li>"""
        )
    return f'<ul class="rows">{"".join(out)}</ul>'


def panel(title: str, body: str, count: str = "") -> str:
    badge = f'<span class="count">{e(count)}</span>' if count != "" else ""
    return f"""<div class="panel">
  <div class="panel-head"><h3>{e(title)}</h3>{badge}</div>
  {body}
</div>"""


def due_panel(events: list[dict]) -> str:
    if not events:
        return panel(
            "Due soon",
            empty("No Canvas feed connected.", "CANVAS_ICS_URL in .env, then scripts/fetch_canvas.py"),
            "0",
        )
    rows = []
    for ev in events[:10]:
        label, sev = until(ev.get("due", ""))
        tag = f'<span class="tag">{e(ev["tag"])}</span>' if ev.get("tag") else ""
        rows.append(
            f"""<li class="row row-compact">
  <div class="row-main">
    <div class="row-who">{tag}<span class="date">{e(ev.get('due', '')[:10])}</span></div>
    <span class="row-subject">{e(ev.get('title'))}</span>
  </div>
  <div class="row-side"><span class="pill pill-{sev}">{e(label)}</span></div>
</li>"""
        )
    return panel("Due soon", f'<ul class="rows">{"".join(rows)}</ul>', str(len(events)))


def docs_panel(docs: list[dict]) -> str:
    if not docs:
        return panel("Documents", empty("Nothing generated yet.", "scripts/gen_doc.py --list"), "0")
    rows = []
    for d in docs[:8]:
        tag = f'<span class="tag">{e(d["tag"])}</span>' if d.get("tag") else ""
        rows.append(
            f"""<li class="row row-compact">
  <div class="row-main">
    <div class="row-who">{tag}<span class="date">{e(d.get('date', ''))}</span></div>
    <a class="row-subject" href="{e(d.get('url') or '#')}">{e(d.get('title') or d.get('path'))}</a>
  </div>
</li>"""
        )
    return panel("Documents", f'<ul class="rows">{"".join(rows)}</ul>', str(len(docs)))


def groupme_panel(log: list[dict]) -> str:
    if not log:
        return panel(
            "GroupMe",
            empty(
                "No connector for GroupMe.",
                'Paste a message to the agent: "log groupme: ..."',
            ),
            "0",
        )
    rows = []
    for m in log[:8]:
        rows.append(
            f"""<li class="row row-compact">
  <div class="row-main">
    <div class="row-who"><span class="who">{e(m.get('from', 'unknown'))}</span>
      <span class="date">{e(m.get('at', '')[:16])}</span></div>
    <span class="row-subject">{e(m.get('text', ''))}</span>
  </div>
</li>"""
        )
    return panel("GroupMe", f'<ul class="rows">{"".join(rows)}</ul>', str(len(log)))


def calendar_panel(entries: list[dict]) -> str:
    """Non Sibi content pipeline, mirroring the sheet's own definition of done:
    a post counts as live only with a real LinkedIn link AND a Live status."""
    if not entries:
        return panel(
            "Content pipeline",
            empty("No Supabase data yet.", "SUPABASE_ANON_KEY in .env, then scripts/fetch_nonsibi.py"),
            "0",
        )
    rows = []
    for c in entries[:10]:
        if c.get("live"):
            label, sev = "live", "calm"
        else:
            label, sev = until(c.get("date", ""))
            if not label:
                label, sev = c.get("status", "not started"), "warn"
        owner = f'<span class="org">{e(c["owner"])}</span>' if c.get("owner") else ""
        title = e(c.get("title", ""))
        subject = (
            f'<a class="row-subject" href="{e(c["link"])}" target="_blank" rel="noopener">{title}</a>'
            if c.get("link")
            else f'<span class="row-subject">{title}</span>'
        )
        rows.append(
            f"""<li class="row row-compact">
  <div class="row-main">
    <div class="row-who"><span class="date">{e(c.get('date', '')[:10])}</span>
      <span class="tag">{e(c.get('channel', ''))}</span>{owner}</div>
    {subject}
  </div>
  <div class="row-side"><span class="pill pill-{sev}">{e(label)}</span></div>
</li>"""
        )
    pending = sum(1 for c in entries if not c.get("live"))
    return panel("Content pipeline", f'<ul class="rows">{"".join(rows)}</ul>', f"{pending} open")


STATUS_COPY = {
    "live": ("Connected", "calm"),
    "blocked": ("Not authorized", "warn"),
    "manual": ("Manual entry", "warn"),
    "none": ("No connector", "critical"),
}
CHANNEL_NAMES = {"personal_gmail": "Personal", "school_outlook": "School", "work_gmail": "Work"}


def chip(name: str, addr: str, label: str, sev: str) -> str:
    return f"""<div class="chip chip-{sev}">
  <span class="dot"></span><span class="chip-name">{e(name)}</span>
  <span class="chip-state">{e(label)}</span><span class="chip-addr">{e(addr)}</span>
</div>"""


def channel_chips(config: dict) -> str:
    chips = []
    for key, acct in (config.get("accounts") or {}).items():
        label, sev = STATUS_COPY.get(acct.get("status", "none"), STATUS_COPY["none"])
        chips.append(
            chip(CHANNEL_NAMES.get(key, key.replace("_", " ").title()),
                 acct.get("address") or "not set", label, sev)
        )
    for name, note in (("Canvas", "ICS feed"), ("GroupMe", "paste-in"), ("LinkedIn", "manual")):
        chips.append(chip(name, note, "No connector", "critical"))
    return "".join(chips)


# --------------------------------------------------------------------------
CSS = """
:root{
  --ground:#FDFAFB; --raise:#FFFFFF; --sunk:#FAF5F7;
  --ink:#2A2430; --ink-2:#665C70; --muted:#9A90A4; --line:#F0E8EE;
  --critical:#D96A7A; --warn:#D9A05B; --calm:#4FAE8B;
  --critical-bg:#FDEEF0; --warn-bg:#FDF4E8; --calm-bg:#E9F7F1;
  --shadow:0 2px 4px rgba(122,90,120,.05), 0 8px 24px rgba(122,90,120,.06);
  --shadow-lift:0 4px 10px rgba(122,90,120,.09), 0 12px 32px rgba(122,90,120,.09);
  --radius:20px; --radius-sm:13px;
  --tone:#9A90A4; --tone-alt:#B3A8BC; --tone-soft:#F7F2F6;
}
@media (prefers-color-scheme:dark){
  :root{
    --ground:#191320; --raise:#221B2B; --sunk:#2A2234;
    --ink:#F2EBF5; --ink-2:#C3B8CC; --muted:#8F849A; --line:#332A3E;
    --critical:#F0929E; --warn:#EDBE7E; --calm:#7FD4B4;
    --critical-bg:#3A2229; --warn-bg:#382C1F; --calm-bg:#1F332C;
    --shadow:0 2px 4px rgba(0,0,0,.22), 0 8px 24px rgba(0,0,0,.20);
    --shadow-lift:0 4px 12px rgba(0,0,0,.3), 0 14px 34px rgba(0,0,0,.26);
  }
}
:root[data-theme="light"]{
  --ground:#FDFAFB; --raise:#FFFFFF; --sunk:#FAF5F7;
  --ink:#2A2430; --ink-2:#665C70; --muted:#9A90A4; --line:#F0E8EE;
  --critical:#D96A7A; --warn:#D9A05B; --calm:#4FAE8B;
  --critical-bg:#FDEEF0; --warn-bg:#FDF4E8; --calm-bg:#E9F7F1;
  --shadow:0 2px 4px rgba(122,90,120,.05), 0 8px 24px rgba(122,90,120,.06);
}
:root[data-theme="dark"]{
  --ground:#191320; --raise:#221B2B; --sunk:#2A2234;
  --ink:#F2EBF5; --ink-2:#C3B8CC; --muted:#8F849A; --line:#332A3E;
  --critical:#F0929E; --warn:#EDBE7E; --calm:#7FD4B4;
  --critical-bg:#3A2229; --warn-bg:#382C1F; --calm-bg:#1F332C;
  --shadow:0 2px 4px rgba(0,0,0,.22), 0 8px 24px rgba(0,0,0,.20);
}

/* Each section carries its own accent via inline --tone-raw. The derived
   tokens must be computed ON the section: a var() resolved at :root can't see
   a --tone-raw that only exists further down the tree. */
section{
  --tone:var(--tone-raw,#9A90A4);
  --tone-alt:var(--tone-alt-raw,#B3A8BC);
  --tone-soft:color-mix(in srgb,var(--tone-raw,#9A90A4) 11%,#ffffff);
}
@media (prefers-color-scheme:dark){
  section{
    --tone:color-mix(in srgb,var(--tone-raw,#9A90A4) 62%,#ffffff);
    --tone-alt:color-mix(in srgb,var(--tone-alt-raw,#B3A8BC) 66%,#ffffff);
    --tone-soft:color-mix(in srgb,var(--tone-raw,#9A90A4) 22%,#191320);
  }
}
:root[data-theme="light"] section{
  --tone:var(--tone-raw,#9A90A4);
  --tone-alt:var(--tone-alt-raw,#B3A8BC);
  --tone-soft:color-mix(in srgb,var(--tone-raw,#9A90A4) 11%,#ffffff);
}
:root[data-theme="dark"] section{
  --tone:color-mix(in srgb,var(--tone-raw,#9A90A4) 62%,#ffffff);
  --tone-alt:color-mix(in srgb,var(--tone-alt-raw,#B3A8BC) 66%,#ffffff);
  --tone-soft:color-mix(in srgb,var(--tone-raw,#9A90A4) 22%,#191320);
}

*{box-sizing:border-box}
body{margin:0; background:var(--ground); color:var(--ink);
  font-family:ui-rounded,"SF Pro Rounded","Hiragino Maru Gothic ProN",
    "Quicksand",system-ui,-apple-system,"Segoe UI",sans-serif;
  font-size:15px; line-height:1.6; -webkit-font-smoothing:antialiased}
.wrap{max-width:1000px; margin:0 auto; padding:46px 22px 84px;
  display:flex; flex-direction:column; gap:22px}

.masthead{display:flex; flex-wrap:wrap; gap:20px; align-items:flex-end;
  justify-content:space-between; padding:0 6px}
.masthead h1{font-size:clamp(27px,3.6vw,37px); font-weight:700; margin:0;
  letter-spacing:-.025em; text-wrap:balance}
.masthead .sub{color:var(--muted); font-size:13.5px; margin:6px 0 0; font-weight:500}
.stamp{font-size:11px; color:var(--muted); text-align:right;
  font-variant-numeric:tabular-nums; line-height:1.6}

.meter{background:var(--raise); border:1px solid var(--line); border-radius:var(--radius);
  padding:19px 22px; box-shadow:var(--shadow); display:flex; flex-direction:column; gap:11px}
.meter-top{display:flex; justify-content:space-between; align-items:baseline; gap:16px; flex-wrap:wrap}
.meter-label{font-size:10.5px; letter-spacing:.1em; text-transform:uppercase;
  color:var(--muted); font-weight:700}
.meter-nums{font-size:12.5px; color:var(--ink-2); font-variant-numeric:tabular-nums; font-weight:500}
.meter-nums b{color:var(--critical); font-size:21px; font-weight:700}
.bar{height:11px; border-radius:99px; background:var(--sunk); overflow:hidden; padding:2px}
.bar span{display:block; background:linear-gradient(90deg,#F0A0AC,var(--critical));
  height:100%; border-radius:99px}
.meter-foot{font-size:12.5px; color:var(--muted); margin:0}

section{background:var(--raise); border:1px solid var(--line);
  border-radius:var(--radius); box-shadow:var(--shadow); overflow:hidden}
.sec-head{display:flex; align-items:center; justify-content:space-between; gap:12px;
  padding:17px 22px; background:var(--tone-soft)}
.sec-title{display:flex; align-items:center; gap:10px; flex-wrap:wrap; min-width:0}
.sec-head h2{font-size:20px; font-weight:700; margin:0; letter-spacing:-.02em; color:var(--tone);
  display:flex; align-items:center; gap:9px}
.sec-head h2::before{content:""; width:11px; height:11px; border-radius:50%;
  background:var(--tone); flex-shrink:0}
.sec-head .who-for{font-size:11.5px; color:var(--muted); font-weight:500}
.count{font-size:11px; color:var(--muted); font-variant-numeric:tabular-nums;
  flex-shrink:0; font-weight:600; background:var(--raise);
  border-radius:99px; padding:3px 11px}
.sec-note{padding:13px 22px; margin:0; font-size:12px; color:var(--muted);
  background:var(--sunk)}

.qlinks{display:flex; flex-wrap:wrap; gap:7px; padding:14px 22px}
.qlink{font-size:12.5px; font-weight:700; text-decoration:none; color:var(--tone);
  border:1.5px solid color-mix(in srgb,var(--tone) 26%,transparent);
  border-radius:99px; padding:6px 15px; background:var(--raise)}
.qlink:hover,.qlink:focus-visible{border-color:var(--tone); background:var(--tone-soft);
  transform:translateY(-1px)}
.qlink{transition:transform .12s ease, background .12s ease, border-color .12s ease}
.qlink.is-todo{color:var(--muted); border-style:dashed; cursor:default}
.qlink.is-todo:hover{transform:none; background:var(--raise); border-color:var(--line)}
.q-confirm{color:var(--warn); font-weight:800}

.rows{list-style:none; margin:0; padding:6px 10px 10px}
.row{display:flex; gap:14px; justify-content:space-between; align-items:flex-start;
  padding:13px 14px; border-radius:var(--radius-sm); border-left:4px solid transparent}
.row + .row{margin-top:3px}
.row:hover{background:var(--sunk)}
.row.is-unread{border-left-color:var(--tone); background:var(--tone-soft)}
.row-main{min-width:0; display:flex; flex-direction:column; gap:2px}
.row-who{display:flex; gap:8px; align-items:baseline; flex-wrap:wrap}
.who{font-weight:700; font-size:13px}
.org,.date{font-size:11.5px; color:var(--muted); font-weight:500}
.date{font-variant-numeric:tabular-nums}
.row-subject{color:var(--ink); text-decoration:none; font-size:14.5px; font-weight:500}
a.row-subject:hover,a.row-subject:focus-visible{color:var(--tone)}
.row-why{margin:2px 0 0; font-size:12px; color:var(--muted)}
.row-side{flex-shrink:0; display:flex; flex-direction:column; align-items:flex-end; gap:7px}
.row-side time{font-size:11px; color:var(--muted); font-variant-numeric:tabular-nums; font-weight:500}

.acts{display:flex; gap:5px}
.act{font:inherit; font-size:11px; font-weight:700; cursor:pointer;
  padding:5px 12px; border-radius:99px; white-space:nowrap;
  border:1.5px solid var(--line); background:var(--raise); color:var(--muted);
  transition:transform .12s ease, background .12s ease, color .12s ease, border-color .12s ease}
.act:hover{border-color:var(--ink-2); color:var(--ink-2); transform:translateY(-1px)}
.act[aria-pressed="true"]{border-color:transparent}
.act-seen[aria-pressed="true"]{background:var(--sunk); color:var(--ink-2)}
.act-replied[aria-pressed="true"]{background:var(--calm-bg); color:var(--calm)}
.act[aria-pressed="true"]::before{content:"\2713\00a0"}
a.act{text-decoration:none; display:inline-flex; align-items:center}
.act-draft{color:var(--tone); border-color:color-mix(in srgb,var(--tone) 30%,transparent)}
.act-draft:hover{background:var(--tone-soft); border-color:var(--tone); color:var(--tone)}
.act-draft.has-draft{background:var(--tone-soft); border-color:var(--tone); font-weight:800}
.act-draft.has-draft::before{content:"\2709\00a0"}
.row.done-seen{background:var(--sunk); opacity:.72}
.row.done-seen .who{color:var(--muted); font-weight:600}
.row.done-seen .row-subject{color:var(--muted)}
.row.done-seen .row-why{display:none}
.row.done-replied{border-left-color:var(--calm); opacity:1}
.row.done-replied .row-subject{text-decoration:line-through; text-decoration-color:var(--muted)}

.panels{display:grid; grid-template-columns:1fr 1fr; gap:14px; padding:4px 12px 14px}
.panels:has(.panel:only-child){grid-template-columns:1fr}
@media (max-width:820px){ .panels{grid-template-columns:1fr} }
.panel{background:var(--sunk); border-radius:var(--radius-sm); padding:4px 4px 8px}
.panel-head{display:flex; align-items:baseline; justify-content:space-between;
  padding:12px 14px 6px}
.panel-head h3{margin:0; font-size:10.5px; font-weight:800; letter-spacing:.1em;
  text-transform:uppercase; color:var(--muted)}
.panel .rows{padding:0 4px 2px}
.panel .row:hover{background:var(--raise)}
.row-compact{padding:9px 12px}
.tag{font-size:10.5px; font-weight:800; color:var(--tone-alt); letter-spacing:.02em}
.pill{display:inline-block; padding:3px 11px; border-radius:99px;
  font-size:10.5px; font-weight:700; white-space:nowrap}
.pill-critical{background:var(--critical-bg); color:var(--critical)}
.pill-warn{background:var(--warn-bg); color:var(--warn)}
.pill-calm{background:var(--calm-bg); color:var(--calm)}

.empty{padding:26px 18px; text-align:center}
.empty p{margin:0; color:var(--ink-2); font-size:13.5px; font-weight:500}
.empty-hint{margin-top:6px !important; font-size:11.5px !important; color:var(--muted) !important;
  font-weight:400 !important; word-break:break-word}

.chips{display:grid; grid-template-columns:repeat(auto-fit,minmax(215px,1fr));
  gap:10px; padding:16px 22px}
.chip{display:grid; grid-template-columns:auto 1fr auto; gap:3px 9px; align-items:center;
  padding:12px 14px; border:1.5px solid var(--line); border-radius:var(--radius-sm);
  background:var(--sunk)}
.dot{grid-area:1/1; width:9px; height:9px; border-radius:50%}
.chip-name{grid-area:1/2; font-size:12.5px; font-weight:700;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis}
.chip-state{grid-area:1/3; font-size:10px; font-weight:700; white-space:nowrap}
.chip-addr{grid-area:2/2/3/4; font-size:10.5px; color:var(--muted);
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
.chip-calm .dot{background:var(--calm)} .chip-calm .chip-state{color:var(--calm)}
.chip-warn .dot{background:var(--warn)} .chip-warn .chip-state{color:var(--warn)}
.chip-critical .dot{background:var(--critical)} .chip-critical .chip-state{color:var(--critical)}

/* ---- calendar ---- */
.cal-nav{display:flex; gap:6px; flex-shrink:0}
.cal-nav button,.add-btn,.layer,#cal-form button{font:inherit; font-size:12px; font-weight:700;
  cursor:pointer; border:1.5px solid var(--line); background:var(--raise);
  color:var(--ink-2); border-radius:99px; padding:6px 13px;
  transition:transform .12s ease, background .12s ease, border-color .12s ease}
.cal-nav button:hover,.add-btn:hover,#cal-form button:hover{border-color:var(--ink-2);
  color:var(--ink); transform:translateY(-1px)}

.layers{display:flex; flex-wrap:wrap; gap:7px; padding:14px 22px; align-items:center}
.layer{display:inline-flex; align-items:center; gap:7px}
.layer .swatch{width:10px; height:10px; border-radius:50%; background:var(--lc); flex-shrink:0}
.layer[aria-pressed="true"]{border-color:var(--lc); color:var(--ink);
  background:color-mix(in srgb,var(--lc) 11%,transparent)}
.layer[aria-pressed="false"]{opacity:.4}
.layer[aria-pressed="false"] .swatch{background:var(--muted)}
.add-btn{margin-left:auto; border-style:dashed}

#cal-form{padding:16px 22px; background:var(--sunk);
  display:flex; flex-direction:column; gap:11px; margin:0 12px 12px;
  border-radius:var(--radius-sm)}
/* an author `display` beats the UA rule behind the hidden attribute */
#cal-form[hidden]{display:none}
.f-row{display:flex; gap:11px; flex-wrap:wrap}
#cal-form label{display:flex; flex-direction:column; gap:4px; font-size:10.5px;
  font-weight:800; color:var(--muted); text-transform:uppercase; letter-spacing:.07em}
#cal-form .f-grow{flex:1; min-width:170px}
#cal-form input,#cal-form select{font:inherit; font-size:13.5px; font-weight:500;
  text-transform:none; letter-spacing:0; color:var(--ink); background:var(--raise);
  border:1.5px solid var(--line); border-radius:11px; padding:7px 11px; min-width:0}
#cal-form input:focus,#cal-form select:focus{outline:2px solid var(--tone); outline-offset:1px}
#f-title{min-width:230px}
.f-actions{display:flex; gap:8px; align-items:center}
.btn-primary{background:var(--tone) !important; color:#fff !important; border-color:transparent !important}
.btn-danger{color:var(--critical) !important; border-color:var(--critical) !important}
#f-hint{font-size:11.5px; color:var(--muted)}

.cal-grid{display:grid; grid-template-columns:repeat(7,minmax(0,1fr));
  gap:4px; padding:0 12px 14px}
.dow{padding:7px 8px; font-size:10px; font-weight:800;
  letter-spacing:.08em; text-transform:uppercase; color:var(--muted); text-align:center}
.day{background:var(--sunk); min-height:94px; padding:7px 8px; display:flex;
  flex-direction:column; gap:4px; cursor:pointer; border:none; text-align:left; font:inherit;
  border-radius:var(--radius-sm); transition:background .12s ease, transform .12s ease}
.day:hover{background:var(--tone-soft); transform:translateY(-1px)}
.day.other{background:transparent}
.day.other .day-n{color:var(--muted); opacity:.45}
.day-n{font-size:11.5px; color:var(--ink-2); font-weight:700;
  font-variant-numeric:tabular-nums; align-self:flex-start}
.day.today{background:var(--tone-soft)}
/* opacity:1 so a today that falls in the previous/next month's trailing days
   isn't dimmed by .day.other into illegibility */
.day.today .day-n{background:var(--tone); color:#fff; border-radius:50%;
  width:22px; height:22px; display:grid; place-items:center; font-weight:800; opacity:1}
.ev{display:flex; align-items:center; gap:5px; font-size:11px; line-height:1.35;
  padding:3px 8px; border-radius:99px; cursor:pointer; border:none; font-family:inherit;
  text-align:left; width:100%; background:color-mix(in srgb,var(--ec) 17%,transparent);
  color:var(--ink); font-weight:600}
.ev:hover{background:color-mix(in srgb,var(--ec) 30%,transparent)}
.ev-t{font-size:9.5px; color:var(--muted); flex-shrink:0; font-weight:700}
.ev-name{overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
.ev.ro{font-style:normal; opacity:.92}
@media (max-width:700px){
  .day{min-height:66px; border-radius:11px}
  .ev-name{font-size:10px}
  .dow{font-size:9px; padding:5px 2px}
  .cal-grid{gap:3px}
}

footer{color:var(--muted); font-size:11.5px; text-align:center; line-height:1.8}
footer code{font-size:11px}
:focus-visible{outline:2px solid var(--tone); outline-offset:2px; border-radius:6px}
@media (prefers-reduced-motion:reduce){ *{transition:none !important; animation:none !important} }
"""

JS = """
// Seen / Replied state lives in this browser, keyed by Gmail thread id, so it
// survives rebuilds of this page. It is not written back to Gmail.
(function () {
  var KEY = 'lbb.marks.v1';
  var marks = {};
  try { marks = JSON.parse(localStorage.getItem(KEY)) || {}; } catch (err) { marks = {}; }

  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(marks)); } catch (err) { /* private mode */ }
  }

  function paint(row) {
    var state = marks[row.dataset.id] || {};
    row.classList.toggle('done-seen', !!state.seen);
    row.classList.toggle('done-replied', !!state.replied);
    row.querySelectorAll('.act').forEach(function (btn) {
      btn.setAttribute('aria-pressed', state[btn.dataset.act] ? 'true' : 'false');
    });
  }

  document.querySelectorAll('.row[data-id]').forEach(paint);

  document.addEventListener('click', function (ev) {
    var btn = ev.target.closest('.act');
    if (!btn) return;
    var row = btn.closest('.row[data-id]');
    if (!row) return;
    var id = row.dataset.id, act = btn.dataset.act;
    marks[id] = marks[id] || {};
    marks[id][act] = !marks[id][act];
    if (act === 'replied' && marks[id].replied) marks[id].seen = true;  // replying implies seen
    save();
    paint(row);
  });
})();

// ---------------------------------------------------------------------------
// Calendar: a month grid with one toggleable layer per workspace. Events you
// add are stored in this browser; Canvas assignments arrive as read-only seed
// data and are re-supplied on every rebuild rather than persisted.
// ---------------------------------------------------------------------------
(function () {
  var grid = document.getElementById('cal-grid');
  if (!grid) return;

  var EVENTS_KEY = 'lbb.calendar.v1';
  var HIDDEN_KEY = 'lbb.calendar.hidden.v1';
  var DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
                'August', 'September', 'October', 'November', 'December'];

  function readJSON(id, fallback) {
    var el = document.getElementById(id);
    if (!el) return fallback;
    try { return JSON.parse(el.textContent); } catch (err) { return fallback; }
  }
  function readStore(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) || fallback; } catch (err) { return fallback; }
  }
  function write(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (err) { /* private mode */ }
  }

  var layers = readJSON('cal-layers', {});
  var seed = readJSON('cal-seed', []);
  var mine = readStore(EVENTS_KEY, []);
  var hidden = new Set(readStore(HIDDEN_KEY, []));

  var form = document.getElementById('cal-form');
  var fTitle = document.getElementById('f-title');
  var fLayer = document.getElementById('f-layer');
  var fDate = document.getElementById('f-date');
  var fTime = document.getElementById('f-time');
  var fNote = document.getElementById('f-note');
  var fDelete = document.getElementById('f-delete');
  var fHint = document.getElementById('f-hint');
  var editing = null;

  var view = new Date();
  view.setDate(1);

  function ymd(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') +
           '-' + String(d.getDate()).padStart(2, '0');
  }
  function color(layer) { return (layers[layer] || {}).color || '#6E7266'; }

  function visibleEvents() {
    return seed.concat(mine).filter(function (ev) { return !hidden.has(ev.layer); });
  }

  function render() {
    document.getElementById('cal-title').textContent = MONTHS[view.getMonth()] + ' ' + view.getFullYear();

    var byDate = {};
    visibleEvents().forEach(function (ev) {
      (byDate[ev.date] = byDate[ev.date] || []).push(ev);
    });

    var first = new Date(view.getFullYear(), view.getMonth(), 1);
    var start = new Date(first);
    start.setDate(1 - first.getDay());          // back up to the Sunday on or before the 1st
    var todayStr = ymd(new Date());

    var html = DOW.map(function (d) { return '<div class="dow">' + d + '</div>'; }).join('');

    for (var i = 0; i < 42; i++) {
      var day = new Date(start);
      day.setDate(start.getDate() + i);
      var key = ymd(day);
      var cls = 'day' + (day.getMonth() !== view.getMonth() ? ' other' : '') +
                (key === todayStr ? ' today' : '');
      var evs = (byDate[key] || []).slice().sort(function (a, b) {
        return (a.time || '99:99').localeCompare(b.time || '99:99');
      });

      html += '<button type="button" class="' + cls + '" data-date="' + key + '">' +
              '<span class="day-n">' + day.getDate() + '</span>' +
              evs.map(function (ev) {
                return '<span class="ev' + (ev.readonly ? ' ro' : '') + '" data-id="' + ev.id +
                       '" style="--ec:' + color(ev.layer) + '" title="' + escapeAttr(ev.title) + '">' +
                       (ev.time ? '<span class="ev-t">' + ev.time + '</span>' : '') +
                       '<span class="ev-name">' + escapeHTML(ev.title) + '</span></span>';
              }).join('') +
              '</button>';
    }
    grid.innerHTML = html;
  }

  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  var escapeAttr = escapeHTML;

  function openForm(ev, date) {
    editing = ev || null;
    form.hidden = false;
    fTitle.value = ev ? ev.title : '';
    fLayer.value = ev ? ev.layer : Object.keys(layers)[0];
    fDate.value = ev ? ev.date : (date || ymd(new Date()));
    fTime.value = ev ? (ev.time || '') : '';
    fNote.value = ev ? (ev.note || '') : '';
    var ro = !!(ev && ev.readonly);
    fDelete.hidden = !ev || ro;
    fHint.textContent = ro
      ? (ev.id && ev.id.indexOf('nonsibi:') === 0
          ? 'From the Non Sibi content sheet — edit it there.'
          : 'From Canvas — edit it in Canvas, not here.')
      : '';
    [fTitle, fLayer, fDate, fTime, fNote].forEach(function (el) { el.disabled = ro; });
    form.querySelector('.btn-primary').disabled = ro;
    if (!ro) fTitle.focus();
  }

  function closeForm() {
    form.hidden = true;
    editing = null;
    fHint.textContent = '';
  }

  grid.addEventListener('click', function (e) {
    var evEl = e.target.closest('.ev');
    if (evEl) {
      var all = seed.concat(mine);
      for (var i = 0; i < all.length; i++) {
        if (all[i].id === evEl.dataset.id) { openForm(all[i]); return; }
      }
      return;
    }
    var dayEl = e.target.closest('.day');
    if (dayEl) openForm(null, dayEl.dataset.date);
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    if (!fTitle.value.trim()) return;
    if (editing && !editing.readonly) {
      editing.title = fTitle.value.trim();
      editing.layer = fLayer.value;
      editing.date = fDate.value;
      editing.time = fTime.value;
      editing.note = fNote.value.trim();
    } else if (!editing) {
      mine.push({
        id: 'e' + Date.now() + Math.random().toString(36).slice(2, 7),
        title: fTitle.value.trim(), layer: fLayer.value, date: fDate.value,
        time: fTime.value, note: fNote.value.trim()
      });
    }
    write(EVENTS_KEY, mine);
    closeForm();
    render();
  });

  fDelete.addEventListener('click', function () {
    if (!editing) return;
    mine = mine.filter(function (ev) { return ev.id !== editing.id; });
    write(EVENTS_KEY, mine);
    closeForm();
    render();
  });

  document.getElementById('f-cancel').addEventListener('click', closeForm);
  document.getElementById('cal-add').addEventListener('click', function () { openForm(null, null); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !form.hidden) closeForm();
  });

  document.getElementById('cal-prev').addEventListener('click', function () {
    view.setMonth(view.getMonth() - 1); render();
  });
  document.getElementById('cal-next').addEventListener('click', function () {
    view.setMonth(view.getMonth() + 1); render();
  });
  document.getElementById('cal-today').addEventListener('click', function () {
    view = new Date(); view.setDate(1); render();
  });

  document.querySelectorAll('.layer').forEach(function (btn) {
    var id = btn.dataset.layer;
    btn.setAttribute('aria-pressed', hidden.has(id) ? 'false' : 'true');
    btn.addEventListener('click', function () {
      if (hidden.has(id)) { hidden.delete(id); } else { hidden.add(id); }
      btn.setAttribute('aria-pressed', hidden.has(id) ? 'false' : 'true');
      write(HIDDEN_KEY, Array.from(hidden));
      render();
    });
  });

  render();
})();
"""


def calendar_section(spaces: list[dict], canvas_events: list[dict],
                     content_items: list[dict]) -> str:
    """Month grid with one toggleable, editable layer per workspace.

    Layer definitions and Canvas seed events are handed to the browser as JSON
    script tags rather than interpolated into the JS, so config stays the
    source of truth for colors and nothing needs escaping twice.
    """
    layers = {
        s["id"]: {"name": s["name"], "color": s.get("accent", "#6E7266")} for s in spaces
    }
    seed = [
        {
            "id": f"canvas:{ev.get('uid') or i}",
            "title": ev.get("title", ""),
            "date": (ev.get("due") or "")[:10],
            "time": (ev.get("due") or "")[11:16],
            "layer": "tulane",
            "readonly": True,
        }
        for i, ev in enumerate(canvas_events)
        if (ev.get("due") or "")[:10]
    ]
    # Non Sibi content posts ride the royal-blue layer, also read-only: the
    # Google Sheet owns them, so editing a copy here would only drift.
    seed += [
        {
            "id": c.get("id") or f"nonsibi:{i}",
            "title": c.get("title", ""),
            "date": (c.get("date") or "")[:10],
            "time": "",
            "layer": "nonsibi",
            "readonly": True,
        }
        for i, c in enumerate(content_items)
        if (c.get("date") or "")[:10]
    ]

    toggles = "".join(
        f'<button type="button" class="layer" data-layer="{e(lid)}" aria-pressed="true" '
        f'style="--lc:{e(meta["color"])}"><span class="swatch"></span>{e(meta["name"])}</button>'
        for lid, meta in layers.items()
    )
    options = "".join(
        f'<option value="{e(lid)}">{e(meta["name"])}</option>' for lid, meta in layers.items()
    )

    return f"""<section id="calendar" style="--tone-raw:#D4779B;--tone-alt-raw:#E8A4BE">
    <div class="sec-head">
      <div class="sec-title"><h2>Calendar</h2><span class="who-for" id="cal-title"></span></div>
      <div class="cal-nav">
        <button type="button" id="cal-prev" aria-label="Previous month">&#8249;</button>
        <button type="button" id="cal-today">Today</button>
        <button type="button" id="cal-next" aria-label="Next month">&#8250;</button>
      </div>
    </div>

    <div class="layers">{toggles}<button type="button" id="cal-add" class="add-btn">+ Add</button></div>

    <form id="cal-form" hidden>
      <div class="f-row">
        <label>Title<input type="text" id="f-title" required maxlength="120" placeholder="e.g. ECON 3010 lecture"></label>
        <label>Layer<select id="f-layer">{options}</select></label>
      </div>
      <div class="f-row">
        <label>Date<input type="date" id="f-date" required></label>
        <label>Time<input type="time" id="f-time"></label>
        <label class="f-grow">Note<input type="text" id="f-note" maxlength="200" placeholder="optional"></label>
      </div>
      <div class="f-actions">
        <button type="submit" class="btn-primary">Save</button>
        <button type="button" id="f-cancel">Cancel</button>
        <button type="button" id="f-delete" class="btn-danger" hidden>Delete</button>
        <span id="f-hint"></span>
      </div>
    </form>

    <div class="cal-grid" id="cal-grid"></div>
    <p class="sec-note">Events you add live in this browser. Canvas assignments and Non Sibi
    content posts are pulled in read-only &mdash; change those in Canvas and the content sheet,
    which stay the source of truth.</p>
  </section>
  <script type="application/json" id="cal-layers">{json.dumps(layers)}</script>
  <script type="application/json" id="cal-seed">{json.dumps(seed)}</script>"""


def workspace_section(space: dict, items: list[dict], panels_html: str, subtitle: str) -> str:
    note = f'<p class="sec-note">{e(space["note"])}</p>' if space.get("note") else ""
    style = (
        f'--tone-raw:{e(space.get("accent", "#6E7266"))};'
        f'--tone-alt-raw:{e(space.get("accent_alt", "#83887E"))}'
    )
    panels = f'<div class="panels">{panels_html}</div>' if panels_html else ""
    return f"""<section style="{style}">
    <div class="sec-head">
      <div class="sec-title"><h2>{e(space['name'])}</h2><span class="who-for">{e(subtitle)}</span></div>
      <span class="count">{len(items)}</span>
    </div>
    {links_bar(space.get('links') or [])}
    {mail_rows(items)}
    {panels}
    {note}
  </section>"""


def build() -> str:
    config = read_config()
    triage = read_json("triage.json")
    canvas = read_json("canvas.json")
    docs = read_json("docs.json")
    groupme = read_json("groupme.json")
    content = read_json("content-calendar.json")

    spaces = config.get("workspaces") or []
    fallback = next((s["id"] for s in spaces if s.get("default")), spaces[-1]["id"] if spaces else "personal")

    buckets: dict[str, list[dict]] = {s["id"]: [] for s in spaces}
    for it in triage.get("items", []):
        buckets.setdefault(route(it, spaces, fallback), []).append(it)

    accounts = config.get("accounts") or {}
    # Which mailbox each workspace reads from, shown next to its title.
    subtitles = {
        "tulane": (accounts.get("school_outlook") or {}).get("address", ""),
        "nonsibi": (accounts.get("work_gmail") or {}).get("address", ""),
        "personal": (accounts.get("personal_gmail") or {}).get("address", ""),
    }

    builders = {
        "due": lambda: due_panel(canvas.get("events", [])),
        "docs": lambda: docs_panel(docs.get("items", [])),
        "groupme": lambda: groupme_panel(groupme.get("items", [])),
        "calendar": lambda: calendar_panel(content.get("items", [])),
    }

    sections = []
    for space in spaces:
        panels_html = "".join(builders[p]() for p in (space.get("panels") or []) if p in builders)
        subtitle = subtitles.get(space["id"]) or space.get("subtitle", "")
        sections.append(workspace_section(space, buckets.get(space["id"], []), panels_html, subtitle))

    stats = triage.get("inbox_stats", {})
    total, unread = stats.get("messages", 0), stats.get("unread", 0)
    sent = stats.get("sent_all_time", 0)
    pct = (unread / total * 100) if total else 0

    owner = config.get("owner", {})
    now = datetime.now(timezone.utc)
    live = sum(1 for a in accounts.values() if a.get("status") == "live")

    meter = ""
    if total:
        meter = f"""<div class="meter">
  <div class="meter-top">
    <span class="meter-label">Personal inbox &mdash; unread share</span>
    <span class="meter-nums"><b>{pct:.1f}%</b> &nbsp;{unread:,} unread of {total:,}</span>
  </div>
  <div class="bar"><span style="width:{pct:.1f}%"></span></div>
  <p class="meter-foot">{sent:,} sent all time &mdash; about one reply per {total // sent if sent else 0} received. Import <code>mail/filters.xml</code> to fix this in one pass.</p>
</div>"""

    return f"""<title>LBB &mdash; Senior Year Command Center</title>
<style>{CSS}</style>
<div class="wrap">

  <header class="masthead">
    <div>
      <h1>Senior Year Command Center</h1>
      <p class="sub">{e(owner.get('name', ''))} &middot; {e(owner.get('school', ''))} &middot; {e(owner.get('term', ''))}</p>
    </div>
    <div class="stamp">built {now:%Y-%m-%d %H:%M} UTC<br>source: {e(triage.get('source', 'unknown'))}</div>
  </header>

  {meter}

  {calendar_section(spaces, canvas.get("events", []), content.get("items", []))}

  {"".join(sections)}

  <section style="--tone-raw:#9B8AC4;--tone-alt-raw:#B9ACD9">
    <div class="sec-head">
      <div class="sec-title"><h2>Channels</h2></div>
      <span class="count">{live} of {len(accounts) + 3} live</span>
    </div>
    <div class="chips">{channel_chips(config)}</div>
    <p class="sec-note">Inactive channels stay visible on purpose &mdash; this panel never shows
    data it doesn't have. See <code>docs/two-gmail-problem.md</code>.</p>
  </section>

  <footer>
    Seen / Replied marks are stored in this browser, not in Gmail.<br>
    Rebuild with <code>python3 scripts/build_dashboard.py</code>
  </footer>

</div>
<script>{JS}</script>
"""


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    page = build()
    OUT.write_text(page)
    print(f"Wrote {OUT.relative_to(ROOT)}  ({len(page):,} bytes)")


if __name__ == "__main__":
    main()
