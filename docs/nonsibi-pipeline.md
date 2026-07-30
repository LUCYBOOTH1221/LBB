# Non Sibi content pipeline

You already have a working pipeline. This repo reads it; it does not replace it.

```
Google Sheet ("Calendar" tab)        <- you edit here, source of truth
        |  AllInOne.gs, on every edit + a 15-min backstop
        v
Supabase `calendar` table            <- read replica
        |                     \
        |                      \--> nonsibi-dashboard.netlify.app  (team-facing)
        v
scripts/fetch_nonsibi.py             <- this repo
        v
data/content-calendar.json
        v
LBB dashboard: Non Sibi panel + royal-blue calendar layer
```

Nothing here writes back. Edit the Sheet; everything downstream follows.

## Keys — read this before pasting anything

Your Apps Script uses the **service_role** key, correctly stored in Script
Properties. That key **bypasses Row Level Security entirely**: it can read,
overwrite, and delete every row in every table.

**It must never go in this repo, in the dashboard HTML, or in any page someone
else can view-source.** Netlify serves your team dashboard publicly; if the
service key were in that page's JavaScript, anyone who opened developer tools
would have full write access to your database.

For anything a browser touches, use the **anon / publishable** key, and only
with RLS enabled:

```sql
alter table calendar enable row level security;

create policy "read calendar" on calendar
  for select to anon using (true);
```

That gives read-only access and nothing more. Without an RLS policy the anon
key returns empty results rather than data — if `fetch_nonsibi.py` reports zero
rows but the sheet has plenty, a missing policy is the first thing to check.

## Setup

```bash
echo 'SUPABASE_ANON_KEY=eyJ...' >> .env     # .env is gitignored
python3 scripts/fetch_nonsibi.py
python3 scripts/build_dashboard.py
```

Options: `--weeks 8` how far ahead to pull, `--back 2` how much history to keep.

The script prefers `SUPABASE_ANON_KEY` and falls back to
`SUPABASE_SERVICE_KEY`, warning when it does. The fallback is acceptable only
because this runs on your machine and writes to a local file.

## What shows up

- **Content pipeline panel** in the Non Sibi workspace: date, channel, owner,
  title, and status. A post counts as **live** only with a real `linkedin.com`
  link *and* a Live status — the same rule `isLive_()` uses in AllInOne.gs, so
  the dashboard and your Wednesday reminder emails never disagree.
- **Royal-blue events** on the calendar, read-only. Clicking one says to edit it
  in the sheet.

## The team

`config.yaml` mirrors the `TEAM` map from AllInOne.gs — Kent, Camille, Andrea,
Auny, Maria, and you. Keep them in sync: the Apps Script resolves "Posting from"
cells against that map to decide who gets nudged, and a name missing from it
silently falls through to a boss-only alert.
