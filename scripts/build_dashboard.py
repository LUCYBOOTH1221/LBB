#!/usr/bin/env python3
"""
Render dashboard/index.html from config.yaml + data/*.json.

Sources that aren't connected render as visibly inactive rather than being
hidden or filled with placeholder rows -- the dashboard should never imply it
knows something it doesn't.

Usage:
    python3 scripts/build_dashboard.py
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "dashboard" / "index.html"

GMAIL_THREAD = "https://mail.google.com/mail/u/0/#inbox/"


# --------------------------------------------------------------------------
# data loading
# --------------------------------------------------------------------------
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
    """Coarse relative age. Precision past 'days' isn't useful for triage."""
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
    """Return (label, severity) for a due date."""
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


# --------------------------------------------------------------------------
# fragments
# --------------------------------------------------------------------------
def empty(message: str, hint: str = "") -> str:
    hint_html = f'<p class="empty-hint">{e(hint)}</p>' if hint else ""
    return f'<div class="empty"><p>{e(message)}</p>{hint_html}</div>'


def reply_rows(items: list[dict]) -> str:
    if not items:
        return empty(
            "Nothing is waiting on you.",
            "This lane fills when a human writes and you haven't answered.",
        )
    out = []
    for it in items:
        unread = " is-unread" if it.get("unread") else ""
        org = f'<span class="org">{e(it["org"])}</span>' if it.get("org") else ""
        tid = e(it.get("id", ""))
        out.append(
            f"""<li class="row{unread}">
  <div class="row-main">
    <div class="row-who"><span class="who">{e(it.get('name') or it.get('from'))}</span>{org}</div>
    <a class="row-subject" href="{GMAIL_THREAD}{tid}" target="_blank" rel="noopener">{e(it.get('subject') or '(no subject)')}</a>
    <p class="row-why">{e(it.get('reason'))}</p>
  </div>
  <div class="row-meta"><time>{e(ago(it.get('received', '')))}</time></div>
</li>"""
        )
    return f'<ul class="rows">{"".join(out)}</ul>'


def due_rows(events: list[dict]) -> str:
    if not events:
        return empty(
            "No Canvas feed connected.",
            "Add CANVAS_ICS_URL to .env, then run scripts/fetch_canvas.py",
        )
    out = []
    for ev in events[:12]:
        label, sev = until(ev.get("due", ""))
        tag = f'<span class="tag">{e(ev["tag"])}</span>' if ev.get("tag") else ""
        due_date = e(ev.get("due", "")[:10])
        out.append(
            f"""<li class="row">
  <div class="row-main">
    <div class="row-who">{tag}<span class="date">{due_date}</span></div>
    <span class="row-subject">{e(ev.get('title'))}</span>
  </div>
  <div class="row-meta"><span class="pill pill-{sev}">{e(label)}</span></div>
</li>"""
        )
    return f'<ul class="rows">{"".join(out)}</ul>'


def doc_rows(docs: list[dict]) -> str:
    if not docs:
        return empty(
            "No documents generated yet.",
            "Ask the agent to draft from a template in docs/templates/",
        )
    out = []
    for d in docs[:10]:
        tag = f'<span class="tag">{e(d["tag"])}</span>' if d.get("tag") else ""
        title = e(d.get("title") or d.get("path"))
        link = e(d.get("url") or "#")
        out.append(
            f"""<li class="row">
  <div class="row-main">
    <div class="row-who">{tag}<span class="date">{e(d.get('date', ''))}</span></div>
    <a class="row-subject" href="{link}">{title}</a>
  </div>
</li>"""
        )
    return f'<ul class="rows">{"".join(out)}</ul>'


STATUS_COPY = {
    "live": ("Connected", "calm"),
    "blocked": ("Not authorized", "warn"),
    "manual": ("Manual entry", "warn"),
    "none": ("No connector", "critical"),
}

# Short enough to sit beside a status label without truncating.
CHANNEL_NAMES = {
    "personal_gmail": "Personal",
    "school_outlook": "School",
    "work_gmail": "Work",
}


def channel_chips(config: dict) -> str:
    chips = []
    for key, acct in (config.get("accounts") or {}).items():
        status = acct.get("status", "none")
        label, sev = STATUS_COPY.get(status, STATUS_COPY["none"])
        name = CHANNEL_NAMES.get(key, key.replace("_", " ").title())
        addr = acct.get("address") or "not set"
        chips.append(chip(name, addr, label, sev))
    for name, note in (("Canvas", "ICS feed"), ("GroupMe", "paste-in")):
        chips.append(chip(name, note, "No connector", "critical"))
    return "".join(chips)


def chip(name: str, addr: str, label: str, sev: str) -> str:
    return f"""<div class="chip chip-{sev}">
  <span class="dot"></span>
  <span class="chip-name">{e(name)}</span>
  <span class="chip-state">{e(label)}</span>
  <span class="chip-addr">{e(addr)}</span>
</div>"""


# --------------------------------------------------------------------------
# page
# --------------------------------------------------------------------------
CSS = """
:root{
  --ground:#FBFAF7; --raise:#FFFFFF; --ink:#171A12; --ink-2:#4A4F42; --muted:#6E7266;
  --line:#E3E2D8; --accent:#3D6B4C; --sky:#40708A;
  --critical:#A03E2C; --warn:#A8762A; --calm:#3D6B4C;
  --critical-bg:#F6E7E2; --warn-bg:#F7EEDC; --calm-bg:#E4EDE5;
  --shadow:0 1px 2px rgba(23,26,18,.05),0 1px 8px rgba(23,26,18,.04);
}
@media (prefers-color-scheme:dark){
  :root{
    --ground:#12140F; --raise:#1A1D16; --ink:#E7E9E0; --ink-2:#B3B8A9; --muted:#878C7C;
    --line:#2A2E24; --accent:#8FBF9C; --sky:#7FADC4;
    --critical:#E08A74; --warn:#D9AC63; --calm:#8FBF9C;
    --critical-bg:#2E1F1A; --warn-bg:#2C2418; --calm-bg:#1C271F;
    --shadow:0 1px 2px rgba(0,0,0,.3),0 1px 8px rgba(0,0,0,.2);
  }
}
:root[data-theme="light"]{
  --ground:#FBFAF7; --raise:#FFFFFF; --ink:#171A12; --ink-2:#4A4F42; --muted:#6E7266;
  --line:#E3E2D8; --accent:#3D6B4C; --sky:#40708A;
  --critical:#A03E2C; --warn:#A8762A; --calm:#3D6B4C;
  --critical-bg:#F6E7E2; --warn-bg:#F7EEDC; --calm-bg:#E4EDE5;
  --shadow:0 1px 2px rgba(23,26,18,.05),0 1px 8px rgba(23,26,18,.04);
}
:root[data-theme="dark"]{
  --ground:#12140F; --raise:#1A1D16; --ink:#E7E9E0; --ink-2:#B3B8A9; --muted:#878C7C;
  --line:#2A2E24; --accent:#8FBF9C; --sky:#7FADC4;
  --critical:#E08A74; --warn:#D9AC63; --calm:#8FBF9C;
  --critical-bg:#2E1F1A; --warn-bg:#2C2418; --calm-bg:#1C271F;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 1px 8px rgba(0,0,0,.2);
}

*{box-sizing:border-box}
body{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
  font-size:15px; line-height:1.5;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1080px; margin:0 auto; padding:40px 24px 72px;
  display:flex; flex-direction:column; gap:32px}

/* header */
.masthead{display:flex; flex-wrap:wrap; gap:24px; align-items:flex-end;
  justify-content:space-between; padding-bottom:24px; border-bottom:2px solid var(--ink)}
.masthead h1{
  font-family:ui-serif,"Iowan Old Style",Georgia,serif;
  font-size:clamp(28px,4vw,40px); font-weight:600; margin:0; letter-spacing:-.015em;
  text-wrap:balance;
}
.masthead .sub{color:var(--muted); font-size:14px; margin:6px 0 0}
.stamp{font-family:ui-monospace,Menlo,monospace; font-size:12px;
  color:var(--muted); text-align:right; font-variant-numeric:tabular-nums}

/* unread meter */
.meter{background:var(--raise); border:1px solid var(--line); border-radius:8px;
  padding:18px 20px; box-shadow:var(--shadow); display:flex; flex-direction:column; gap:12px}
.meter-top{display:flex; justify-content:space-between; align-items:baseline; gap:16px; flex-wrap:wrap}
.meter-label{font-size:11px; letter-spacing:.09em; text-transform:uppercase;
  color:var(--muted); font-weight:600}
.meter-nums{font-family:ui-monospace,Menlo,monospace; font-variant-numeric:tabular-nums;
  font-size:13px; color:var(--ink-2)}
.meter-nums b{color:var(--critical); font-size:20px; font-weight:600}
.bar{height:10px; border-radius:5px; background:var(--calm-bg); overflow:hidden; display:flex}
.bar span{display:block; background:var(--critical); height:100%}
.meter-foot{font-size:13px; color:var(--muted); margin:0}

/* sections */
section{background:var(--raise); border:1px solid var(--line); border-radius:8px;
  box-shadow:var(--shadow); overflow:hidden}
.sec-head{display:flex; align-items:baseline; justify-content:space-between; gap:12px;
  padding:16px 20px; border-bottom:1px solid var(--line)}
.sec-head h2{font-family:ui-serif,"Iowan Old Style",Georgia,serif;
  font-size:18px; font-weight:600; margin:0; letter-spacing:-.01em}
.sec-head .count{font-family:ui-monospace,Menlo,monospace; font-size:12px;
  color:var(--muted); font-variant-numeric:tabular-nums}
.sec-note{padding:0 20px; margin:12px 0 0; font-size:13px; color:var(--muted)}

/* align-items:start keeps a short/empty panel at its natural height
   instead of stretching it into a void beside a taller sibling */
.split{display:grid; grid-template-columns:1fr 1fr; gap:24px; align-items:start}
@media (max-width:760px){ .split{grid-template-columns:1fr} }

/* rows */
.rows{list-style:none; margin:0; padding:0}
.row{display:flex; gap:16px; justify-content:space-between; align-items:flex-start;
  padding:14px 20px; border-bottom:1px solid var(--line)}
.row:last-child{border-bottom:none}
.row.is-unread{border-left:3px solid var(--critical); padding-left:17px}
.row-main{min-width:0; display:flex; flex-direction:column; gap:3px}
.row-who{display:flex; gap:8px; align-items:baseline; flex-wrap:wrap}
.who{font-weight:600; font-size:13px}
.org,.date{font-size:12px; color:var(--muted)}
.date{font-family:ui-monospace,Menlo,monospace; font-variant-numeric:tabular-nums}
.row-subject{color:var(--ink); text-decoration:none; font-size:15px;
  border-bottom:1px solid transparent}
a.row-subject:hover,a.row-subject:focus-visible{border-bottom-color:var(--accent); color:var(--accent)}
.row-why{margin:2px 0 0; font-size:12.5px; color:var(--muted); font-style:italic}
.row-meta{flex-shrink:0; text-align:right}
.row-meta time{font-family:ui-monospace,Menlo,monospace; font-size:12px;
  color:var(--muted); font-variant-numeric:tabular-nums}

.tag{font-family:ui-monospace,Menlo,monospace; font-size:11px; font-weight:600;
  color:var(--sky); letter-spacing:.02em}
.pill{display:inline-block; padding:2px 9px; border-radius:99px; font-size:11.5px;
  font-weight:600; white-space:nowrap}
.pill-critical{background:var(--critical-bg); color:var(--critical)}
.pill-warn{background:var(--warn-bg); color:var(--warn)}
.pill-calm{background:var(--calm-bg); color:var(--calm)}

/* empty states */
.empty{padding:28px 20px; text-align:center}
.empty p{margin:0; color:var(--ink-2); font-size:14px}
.empty-hint{margin-top:6px !important; font-size:12.5px !important; color:var(--muted) !important;
  font-family:ui-monospace,Menlo,monospace}

/* channel chips */
.chips{display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:10px; padding:16px 20px}
/* two rows: [dot | name | state] over [address spanning the text columns],
   so a long name never has to wrap against the status label.
   Every cell is placed explicitly -- auto-placement gets this wrong. */
.chip{display:grid; grid-template-columns:auto 1fr auto; gap:2px 9px;
  align-items:center; padding:10px 12px; text-align:left;
  border:1px solid var(--line); border-radius:6px; background:var(--ground)}
.dot{grid-area:1/1; width:8px; height:8px; border-radius:50%}
.chip-name{grid-area:1/2; font-size:13px; font-weight:600;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis}
.chip-state{grid-area:1/3; font-size:11px; font-weight:600; white-space:nowrap}
.chip-addr{grid-area:2/2/3/4; font-size:11.5px; color:var(--muted);
  font-family:ui-monospace,Menlo,monospace;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
.chip-calm .dot{background:var(--calm)} .chip-calm .chip-state{color:var(--calm)}
.chip-warn .dot{background:var(--warn)} .chip-warn .chip-state{color:var(--warn)}
.chip-critical .dot{background:var(--critical)} .chip-critical .chip-state{color:var(--critical)}

footer{color:var(--muted); font-size:12.5px; text-align:center; line-height:1.7}
footer code{font-family:ui-monospace,Menlo,monospace; font-size:12px}
:focus-visible{outline:2px solid var(--accent); outline-offset:2px; border-radius:2px}
@media (prefers-reduced-motion:reduce){ *{transition:none !important; animation:none !important} }
"""


def build() -> str:
    config = read_config()
    triage = read_json("triage.json")
    canvas = read_json("canvas.json")
    docs = read_json("docs.json")

    items = triage.get("items", [])
    replies = [i for i in items if i.get("lane") == "reply"]
    watch = [i for i in items if i.get("lane") != "reply"]
    events = canvas.get("events", [])

    stats = triage.get("inbox_stats", {})
    total = stats.get("messages", 0)
    unread = stats.get("unread", 0)
    sent = stats.get("sent_all_time", 0)
    pct = (unread / total * 100) if total else 0

    owner = config.get("owner", {})
    now = datetime.now(timezone.utc)

    meter = ""
    if total:
        meter = f"""<div class="meter">
  <div class="meter-top">
    <span class="meter-label">Personal inbox &mdash; unread share</span>
    <span class="meter-nums"><b>{pct:.1f}%</b> &nbsp;{unread:,} unread of {total:,}</span>
  </div>
  <div class="bar"><span style="width:{pct:.1f}%"></span></div>
  <p class="meter-foot">{sent:,} messages sent, all time &mdash; roughly one reply for every {total // sent if sent else 0} received. Import <code>mail/filters.xml</code> to cut this down.</p>
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

  <section>
    <div class="sec-head">
      <h2>Waiting on you</h2>
      <span class="count">{len(replies)}</span>
    </div>
    {reply_rows(replies)}
  </section>

  <div class="split">
    <section>
      <div class="sec-head">
        <h2>Due soon</h2>
        <span class="count">{len(events)}</span>
      </div>
      {due_rows(events)}
    </section>

    <section>
      <div class="sec-head">
        <h2>Keep an eye on</h2>
        <span class="count">{len(watch)}</span>
      </div>
      {reply_rows(watch) if watch else empty("Nothing flagged.")}
    </section>
  </div>

  <section>
    <div class="sec-head">
      <h2>Documents</h2>
      <span class="count">{len(docs.get('items', []))}</span>
    </div>
    {doc_rows(docs.get('items', []))}
  </section>

  <section>
    <div class="sec-head">
      <h2>Channels</h2>
      <span class="count">{sum(1 for a in (config.get('accounts') or {}).values() if a.get('status') == 'live')} of {len(config.get('accounts') or {}) + 2} live</span>
    </div>
    <div class="chips">{channel_chips(config)}</div>
    <p class="sec-note" style="padding-bottom:16px">Inactive channels stay visible on purpose &mdash; this panel never
    shows data it doesn't have. See <code>docs/two-gmail-problem.md</code> and <code>docs/canvas-and-groupme.md</code>.</p>
  </section>

  <footer>
    Rebuild with <code>python3 scripts/build_dashboard.py</code><br>
    Reads <code>config.yaml</code>, <code>data/triage.json</code>, <code>data/canvas.json</code>, <code>data/docs.json</code>
  </footer>

</div>
"""


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    page = build()
    OUT.write_text(page)
    print(f"Wrote {OUT.relative_to(ROOT)}  ({len(page):,} bytes)")


if __name__ == "__main__":
    main()
