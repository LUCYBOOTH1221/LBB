# Build brief: a personal command center

Paste this whole file into Claude Code and say **"build this for me."** Answer its
questions about your own accounts and it will produce the system described below.

Everything here is generic. Fill in your own addresses, people, and URLs.

---

## What it is

A single generated HTML page that shows, across every account you use:

- what mail is waiting on a reply, grouped by **workspace** (school / job / personal)
- an editable calendar with a colored, toggleable layer per workspace
- upcoming deadlines pulled from your LMS
- documents you've generated
- a status panel showing which sources are actually connected

Plus a set of scripts that generate it, and a mail-filter file that does the
heavy cleanup.

**The core design rule:** the page never invents data. If a source isn't
connected, its panel says so. That sounds obvious and is the single most
important decision in the whole thing — a dashboard that quietly shows stale or
fabricated rows is worse than no dashboard.

---

## If you only want the school dashboard

Most of this generalizes, but a school-only build is a smaller, cleaner target.
Cut it down to:

**Workspaces:** just two — `school` and `personal` (the catch-all). Skip the
job/work sections entirely.

**Panels for the school workspace:**

| Panel | Source | Notes |
|---|---|---|
| Due soon | LMS iCal feed | The single highest-value panel. Do this first. |
| Mail | School mail, if a connector exists | Otherwise the section still earns its place as a links bar. |
| Documents | Local templates | Reading responses, meeting notes, lecture notes |

**Quick links** — the cheapest win in the whole project. A links bar in the
school section pointing at the student portal, class-schedule search, the LMS,
and webmail. Five minutes of config, used every day.

**Class tagging.** Put your courses in config:

```yaml
classes:
  - { tag: POLS-4010, name: Senior Seminar, meets: [Tue, Thu] }
  - { tag: ECON-3010, name: Econometrics,   meets: [Mon, Wed, Fri] }
```

The LMS feed puts the course name in each event's `CATEGORIES` field. Match on
that to attach a `tag`, then key everything downstream off the same tag —
calendar chips, document filenames (`YYYY-MM-DD-<tag>-<slug>.md`), and mail
labels. One vocabulary across the whole system.

**The iCal parser is the only fiddly part.** Don't add a dependency; ~60 lines
of standard library covers it. Three things the spec requires:

- **Line folding** — long lines wrap with a leading space or tab on
  continuations; unfold before parsing or titles get truncated mid-word.
- **Two date formats** — `YYYYMMDD` for all-day and `YYYYMMDDTHHMMSSZ` for
  timed. Handle both or half your assignments vanish.
- **Escaping** — `\,` `\;` `\n` `\\` in text fields.

Ask Claude for the parser and hand it a small sample `.ics` to test against
before pointing it at the live feed.

**Skip for now:** the work/marketing sections, any external database sync, and
the whole two-Gmail problem. Add them later if a job needs it.

---

## Read this before you start: what does *not* work

I lost time discovering these. Check them against your own setup first.

| Constraint | Consequence |
|---|---|
| **The Gmail connector authorizes exactly ONE Google account.** | You cannot have personal + work Gmail live simultaneously. Not a settings toggle, not a paid-plan thing. Pick one, and forward the other into it, or use Workspace delegation. |
| **The Microsoft 365 connector is read-only.** | It can *search* Outlook mail and calendar. It cannot label, move, or archive. Outlook cleanup must be done with Outlook Rules, by hand, once. |
| **There is no Canvas connector.** | Use the per-user **iCal feed** instead (Canvas → Calendar → Calendar Feed). Read-only, no admin approval, updates when a professor moves a due date. |
| **There is no GroupMe connector.** | Either paste messages in manually, or register a GroupMe **bot with a callback URL** that POSTs each message to a small endpoint. |
| **University IT often blocks third-party OAuth consent.** | The M365 connector may fail with an admin-approval error. That's policy, not a bug. Plan for the school panel to stay empty. |

Ask Claude to verify these against *your* connectors before designing around
them. Mine may not match yours.

---

## The mail problem, and the right shape of fix

My inbox was **~74,000 messages, ~72,500 unread, 341 sent ever.** Roughly one
reply per 216 received.

Two findings that will probably hold for you too:

1. **The worst senders are not newsletters.** They're per-transaction bank
   alerts (one email per coffee) and ride-share receipts that send **two**
   near-identical emails per trip. Those two senders out-produced every
   retailer combined. Check yours before assuming it's shopping mail.
2. **Real correspondence was buried and unread** underneath — including
   messages from a nonprofit CEO and time-boxed university program deadlines
   addressed by name.

### The architecture that matters

| Scope | Mechanism | Why |
|---|---|---|
| The historical backlog | **Gmail filters, applied retroactively** | Server-side, one pass, instant |
| Today's mail | The agent | Judgment a rule can't make |

**Do not let the agent clean the backlog through the API.** I tried. Each
thread is one API call, which is one permission prompt. It is unusably slow and
it buries you in prompts. Gmail's own filter engine does the whole backlog with
one checkbox.

The winning move: have Claude generate an **importable Gmail filter XML file**
from your config, then import it at
*Settings → Filters and Blocked Addresses → Import filters*, ticking
**"Apply new filters to existing conversations."**

Gmail's filter format is an Atom feed:

```xml
<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns='http://www.w3.org/2005/Atom'
      xmlns:apps='http://schemas.google.com/apps/2006'>
  <entry>
    <category term='filter'></category>
    <title>Mail Filter</title>
    <apps:property name='from' value='{a@x.com b@y.com}'/>
    <apps:property name='label' value='Shopping'/>
    <apps:property name='shouldArchive' value='true'/>
    <apps:property name='shouldMarkAsRead' value='true'/>
  </entry>
</feed>
```

Useful properties: `from`, `to`, `subject`, `hasTheWord`, `shouldArchive`,
`shouldMarkAsRead`, `shouldAlwaysMarkAsImportant`, `shouldNeverSpam`,
`shouldNeverMarkAsImportant`, `label`.

Rules that made the difference:

- **Put a protect-VIPs rule first** — bosses, professors, and whole trusted
  domains get `shouldAlwaysMarkAsImportant` + `shouldNeverSpam`, before any
  noise rule runs.
- **Archive, never delete.** Archive is reversible and still searchable.
- **Newsletters archive but stay UNREAD** so the label keeps a badge. Receipts
  archive *and* mark read, because you only ever want those from search.
- Chunk senders ~20 per filter; Gmail rejects over-long queries.

---

## Repo layout

```
config.yaml              single source of truth: accounts, people, workspaces, noise
CLAUDE.md                standing brief + hard limits for the agent
dashboard/index.html     generated — never hand-edit
mail/
  filters.xml            generated — import into Gmail
  README.md              what's actually in the inbox
  outlook-rules.md       Outlook rules, since its connector can't write
docs/
  templates/             document templates
scripts/
  gen_filters.py         config.yaml -> mail/filters.xml
  fetch_canvas.py        LMS iCal feed -> data/canvas.json
  fetch_content.py       your work DB/API -> data/content-calendar.json
  gen_doc.py             template -> docs/generated/
  build_dashboard.py     everything -> dashboard/index.html
data/                    JSON snapshots (gitignored except a seed)
.env                     secrets — GITIGNORED
```

Everything reads `config.yaml`. Change a sender there, regenerate, re-import.

---

## config.yaml shape

```yaml
owner: { name: Your Name, school: Your School, term: Fall 2026 }

accounts:
  personal_gmail: { address: you@gmail.com,      status: live }
  school_outlook: { address: you@school.edu,     status: blocked }
  work_gmail:     { address: you@company.com,    status: blocked }

people:                       # drives the protect rule AND dashboard priority
  - { handle: boss1, name: A Boss, address: boss@company.com,
      priority: high, workspace: work }
  - { handle: prof,  name: A Professor, address: prof@school.edu,
      priority: high, workspace: research }

never_filter_domains: [school.edu, company.com]

workspaces:                   # each becomes a colored section + calendar layer
  - id: school
    name: School
    accent: "#006747"
    match: [school.edu]       # routes mail by sender
    links:
      - { label: "Portal",   url: "https://..." }
      - { label: "LMS",      url: "https://..." }
    panels: [due, docs]

  - id: research
    name: Research
    accent: "#6D4AA6"
    match: [prof@school.edu]  # an EXACT ADDRESS — see the routing gotcha below
    panels: [messages]

  - id: work
    name: Work
    accent: "#2A4FC9"
    match: [company.com]
    panels: [calendar]

  - id: personal
    name: Personal
    accent: "#B0603A"
    default: true             # catches everything unmatched
    match: []

noise:                        # measure YOUR OWN inbox; don't copy mine
  transaction_alerts: [alerts@yourbank.com]
  duplicate_receipts: [noreply@rideshare.com]
  retail: [...]
  newsletters: [...]
```

---

## Gotchas that cost me real time

These are the parts worth handing your Claude verbatim.

**1. Exact addresses must outrank domain matches.**
My research supervisor's address is `@school.edu`, and the School workspace
claims that whole domain — so his mail landed in School purely because that
workspace was listed first. Routing must resolve in three passes: explicit
override, then **exact addresses across all workspaces**, then domains.
Otherwise config ordering silently decides your routing.

**2. CSS custom properties resolve where they're declared, not where they're used.**
Giving each section its own accent via an inline `--tone-raw` fails if you
compute `--tone: var(--tone-raw)` at `:root` — root can't see a variable set
further down the tree. Compute the derived tokens **on the section selector**.
For dark mode, lighten with `color-mix(in srgb, var(--tone-raw) 60%, white)`.

**3. `\2713` in a CSS string inside Python is an OCTAL ESCAPE.**
`content:"\2713\00a0"` becomes `¹3\x00a0` before CSS ever sees it, and your
checkmarks render as literal garbage. Use the actual `✓` character, or a raw
string. I only caught this by **screenshotting the rendered page** — it was
invisible in the source.

**4. The `hidden` attribute loses to any author `display` rule.**
`<form hidden>` styled with `display:flex` is visible. Add `[hidden]{display:none}`.

**5. On Windows, `Path.read_text()` / `write_text()` default to cp1252, not UTF-8.**
Any non-ASCII character — a checkmark, an em-dash — crashes with
`UnicodeEncodeError`. **Pass `encoding="utf-8"` on every single file read and
write.** This bites on Windows and passes silently on macOS/Linux, so it's easy
to ship broken.

**6. Gmail's API caps result counts at 201.** You cannot get a true total from
it. Get real counts from the Gmail web UI.

**7. `display:contents` breaks CSS grid auto-placement.** If a wrapper div uses
it, place every child explicitly with `grid-area`.

---

## Interaction details worth copying

- **Seen / Draft / Replied buttons on every message row.** State keyed by thread
  ID in `localStorage`, so it survives regenerating the page.
- **Seen HIDES the row** — dimming isn't enough; the point is clearing the
  screen. The section's count ticks down, and a "Show N filed" link brings them
  back. Never destroy state, just hide it.
- **Draft** opens Gmail compose prefilled:
  `https://mail.google.com/mail/?view=cm&fs=1&to=SENDER&su=Re:%20SUBJECT`
  Gmail has **no public deep link that opens a reply inside an existing
  thread** — for a genuinely threaded draft the agent has to write it through
  the API.
- **Calendar layers** toggle per workspace; events and hidden-layer state both
  persist in `localStorage`.
- **Data pulled from an external system is read-only in the UI.** Clicking it
  says "edit this in <source>." Otherwise you get two sources of truth and
  silent drift.

---

## Secrets

**Never put a database service-role key in a page.** If you sync a spreadsheet
to something like Supabase, the `service_role` key bypasses row-level security
entirely — anyone who views source on a deployed page gets full read/write.

- `service_role` → server-side only (e.g. Apps Script Properties)
- `anon`/publishable → browsers, and only with RLS enabled:

```sql
alter table your_table enable row level security;
create policy "read" on your_table for select to anon using (true);
```

An anon key **without** a policy returns *empty results, not an error* — so
"zero rows" usually means a missing policy, not a missing key.

Put every secret in `.env` and gitignore it. An LMS calendar-feed URL is a
bearer credential: anyone with it reads your whole schedule.

---

## Setup (Windows)

```powershell
git clone <your-repo>
cd <your-repo>
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install pyyaml

# secrets — one per line, .env is gitignored
"CANVAS_ICS_URL=https://..." | Out-File -Encoding utf8 -Append .env

python scripts\gen_filters.py
python scripts\fetch_canvas.py
python scripts\build_dashboard.py
start dashboard\index.html
```

If PowerShell blocks the venv activation:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

**macOS / Linux:** same, but `python3`, `source .venv/bin/activate`,
`echo '...' >> .env`, and `open dashboard/index.html`.

Requires **Python 3.11+** and `pyyaml`. Everything else is standard library —
no build step, no npm, no framework.

---

## Prompt to paste into Claude

> I want a personal command center: one generated HTML dashboard covering my
> mail, deadlines, documents, and messages across several accounts, plus scripts
> that build it.
>
> Start by checking which connectors I actually have and telling me honestly
> what can't be built — do not design around integrations that don't exist, and
> do not put placeholder data in any panel. A source that isn't connected must
> render as visibly "not connected."
>
> Then:
> 1. Measure my actual inbox and tell me the real top senders by volume before
>    proposing any filters.
> 2. Generate an importable Gmail filter XML from a config file, with a
>    protect-VIPs rule first. Archive, never delete. Don't clean the backlog
>    through the API — that's one permission prompt per thread.
> 3. Build a dashboard split into workspaces I define in config, each with its
>    own accent color, quick links, mail lane, and panels.
> 4. Give every message row Seen / Draft / Replied buttons. Seen hides the row
>    and decrements the section count, with a "show filed" escape hatch. Persist
>    in localStorage.
> 5. Add a month calendar with one toggleable, editable layer per workspace.
>    Data pulled from external systems is read-only.
> 6. Pass `encoding="utf-8"` on every file read and write — I'm on Windows.
> 7. Screenshot the rendered page in both light and dark mode before telling me
>    it works. Character-encoding and CSS-cascade bugs are invisible in source.
>
> Ask me for my accounts, the people who matter, and my workspaces first.

### Shorter version, school only

> Build me a school dashboard: one generated HTML page with my upcoming
> assignments, my school mail, quick links to my student portal / class schedule
> / LMS, and documents I generate from templates. Python + standard library, no
> framework, no build step.
>
> First tell me honestly which of my accounts you can actually reach — if
> there's no connector for my LMS, say so and use its iCal calendar feed
> instead (Calendar → Calendar Feed). A panel with no data source must render as
> visibly "not connected," never with placeholder rows.
>
> Then:
> 1. Write an iCal parser using only the standard library. Handle RFC 5545 line
>    folding, both `YYYYMMDD` and `YYYYMMDDTHHMMSSZ` date forms, and escaped
>    characters. Test it against a sample file I give you before hitting the
>    live feed.
> 2. Read my classes from a config file and tag each assignment with its course
>    code. Use that same tag for document filenames and calendar chips.
> 3. Build the page with a school section — accent it in my school's colors —
>    holding a quick-links bar, a deadlines panel sorted by urgency, and a
>    documents panel.
> 4. Add a month calendar where assignments appear read-only (I edit those in
>    the LMS) and I can add my own events on a separate layer. Persist mine in
>    localStorage.
> 5. Pass `encoding="utf-8"` on every file read and write — I'm on Windows.
> 6. Keep my calendar-feed URL in a gitignored `.env`. It's a credential:
>    anyone holding it can read my whole schedule.
> 7. Screenshot the rendered page in light and dark mode before telling me it
>    works.
>
> Ask me for my school, my classes, and my portal URLs first.
