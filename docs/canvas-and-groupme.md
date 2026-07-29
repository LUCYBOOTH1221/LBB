# Canvas and GroupMe

Neither has a Claude connector. I checked the registry — Canvas/Instructure and
GroupMe both return nothing. That isn't a permissions problem you can fix by
authorizing something; the integrations don't exist.

Both still have a way in. Canvas has a genuinely good one.

---

## Canvas — use the calendar feed

Canvas publishes a per-user iCal feed containing every assignment and event
across all your enrolled courses. It's read-only, it needs no admin approval,
and it updates automatically when a professor changes a due date.

### Get your feed URL

1. Canvas → **Calendar** (left sidebar)
2. Scroll the right-hand panel to the bottom → **Calendar Feed**
3. Copy the `https://…/feeds/calendars/user_….ics` URL

Treat it like a password. Anyone with it can read your whole academic schedule.
Put it in `.env`, which is gitignored — **never** in `config.yaml`, which is
committed.

```bash
echo 'CANVAS_ICS_URL=https://tulane.instructure.com/feeds/calendars/user_xxx.ics' >> .env
```

Then:

```bash
python3 scripts/fetch_canvas.py
```

That writes `data/canvas.json`, which the dashboard reads for the "Due this
week" panel.

### Class tagging

Canvas puts the course name in each event's `CATEGORIES` field. The fetch script
maps those onto the `classes:` list in `config.yaml`, so once you fill in your
Fall 2026 courses with a `tag`, everything downstream — dashboard columns,
document filenames, Gmail labels — keys off the same tag.

Fill `classes:` in after registration is final.

### If you need more than due dates

Canvas has a full REST API (grades, submissions, announcements, files) behind a
personal access token: **Account → Settings → New Access Token**. That's a
larger build and the ICS feed covers the actual need — deadlines on the
dashboard. Start with the feed; add the API only if you find yourself wanting
grades in there too.

---

## GroupMe — paste-in capture

GroupMe's API exists but requires registering a developer application and
handling OAuth, which is a disproportionate amount of work for reading one
boss's messages.

The pragmatic path: paste the message to the agent.

```
"log groupme: [Boss] can you have the deck ready by Thursday?"
```

The agent appends to `data/groupme-log.md` with a timestamp, extracts any action
item and deadline, and surfaces it in the daily brief alongside email — so the
tooling boss's requests sit in the same ranked list as everything else, which is
the point of the whole system.

It's manual. It's also thirty seconds, and it means one channel can't quietly
become the one you stop checking.

### If GroupMe volume gets heavy

Two escalation options, in order of effort:

1. **GroupMe bot callback** — GroupMe lets you register a bot with a callback
   URL that POSTs every message in a group. Point it at a small endpoint that
   appends to the log file. No OAuth dance, no polling.
2. **Full API client** — only if you need history, DMs, or multiple groups.

Neither is worth building until the paste-in path proves too slow.
