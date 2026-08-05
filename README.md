# LBB — Senior Year Command Center

One place for mail, deadlines, documents, and messages, with an agent that
triages the pile and a dashboard that shows only what needs you.

Built for Fall 2026. Start with **[Start here](#start-here)**.

---

## The situation

Measured on `lbb122104@gmail.com`, 2026-07-29:

| | |
|---|---|
| Messages in inbox | **73,969** |
| Unread | **72,517** (98.0%) |
| Sent, all time | 341 |

Roughly one reply for every 216 messages received. Buried in there, unread, were
messages from the CEO of Make-A-Wish Greater Bay Area and two from American
University's Washington Semester Program addressed to you by name.

That's the actual problem. Not tidiness — **things from real people are getting
lost.** Every design decision here follows from that.

## What's connected, and what isn't

| Source | State | Notes |
|---|---|---|
| Personal Gmail | **live** | read, label, draft. Never sends, never deletes. |
| Google Drive | **live** | |
| School Outlook | not authorized | Microsoft 365 connector exists — [needs your OK](mail/outlook-rules.md) |
| Work Gmail | blocked | one Gmail account per connector — [three workarounds](docs/two-gmail-problem.md) |
| Canvas | no connector | use the [iCal feed](docs/canvas-and-groupme.md) |
| GroupMe | no connector | [paste-in capture](docs/canvas-and-groupme.md) |

Three of the six things you asked for have no integration available today. Two
have good workarounds, one (Outlook) just needs authorizing. **Nothing here
fakes data for a source that isn't connected** — unconnected panels render as
inactive on purpose, so the dashboard is never confidently wrong.

## Start here

**1. Cut the noise.** The single highest-leverage thing, and it takes five
minutes:

```bash
python3 scripts/gen_filters.py     # writes mail/filters.xml
```

Gmail → Settings → Filters and Blocked Addresses → **Import filters** → pick
`mail/filters.xml` → tick **"Apply new filters to existing conversations."**

Eight rules covering 47 senders. The first rule protects Betsy, Tulane,
American, and Make-A-Wish before anything else runs. Nothing is deleted —
archive only, all reversible. Full detail in **[mail/README.md](mail/README.md)**.

The top two offenders aren't retailers, by the way. They're Discover
(one alert per coffee) and Uber (two emails per ride).

**2. Decide the work-Gmail question.** Read
**[docs/two-gmail-problem.md](docs/two-gmail-problem.md)**. It needs a
conversation with your boss, so start it early.

**3. Add Canvas once you've registered.** Grab your calendar feed URL, then:

```bash
echo 'CANVAS_ICS_URL=https://...' >> .env
python3 scripts/fetch_canvas.py
```

**4. Fill in `config.yaml`.** Lines marked `CONFIRM:` are inferred from your
mail and unverified — the classes list is empty, work Gmail is unset, and the
GroupMe boss has no name yet.

**5. Build the dashboard.**

```bash
python3 scripts/build_dashboard.py && open dashboard/index.html
```

## How it's put together

```
config.yaml              single source of truth — accounts, people, noise
CLAUDE.md                standing brief for the agent
dashboard/index.html     generated; open it directly
mail/
  README.md              what's in the inbox and how the filters work
  filters.xml            generated; import into Gmail
  outlook-rules.md       Outlook is read-only, so rules go in Outlook
docs/
  two-gmail-problem.md   why work Gmail can't connect, and what to do
  canvas-and-groupme.md  ICS feed setup, GroupMe capture
  templates/             document templates
scripts/
  gen_filters.py         config.yaml  -> mail/filters.xml
  fetch_canvas.py        ICS feed     -> data/canvas.json
  gen_doc.py             template     -> docs/generated/
  build_dashboard.py     everything   -> dashboard/index.html
```

Everything reads from `config.yaml`. Add a sender to `noise:`, regenerate,
re-import — never hand-edit `filters.xml` or `dashboard/index.html`.

## The split that makes this work

| Scope | Handled by | Why |
|---|---|---|
| 72,000 old messages | Gmail filters | server-side, one pass, instant |
| Today's mail | the agent | judgment machines can't make |

Clearing the backlog through the API would be ~72,000 calls. Gmail's own filter
engine does it with one checkbox. The agent never brute-forces the backlog, and
`CLAUDE.md` forbids it.

## Standing limits on the agent

- Never sends email — drafts only, you send.
- Never deletes. Archive is the strongest action allowed.
- Never modifies more than 50 threads without asking.
- Never filters a sender who isn't already listed in `config.yaml`.
- Never invents a citation, deadline, or quotation in a generated document.

## Requirements

Python 3.11+ and PyYAML (`pip install pyyaml`). Everything else is standard
library.
