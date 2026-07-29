# Mail cleanup

## What's actually in the inbox

Measured on `lbb122104@gmail.com`, 2026-07-29:

| | |
|---|---|
| Messages in inbox | 73,969 |
| Unread | 72,517 |
| Threads | 73,088 |
| Sent, ever | 341 |

That last row is the one worth staring at. **341 sent against 73,969 received.**
This is not a mailbox that has an organization problem. It is a mailbox that is
99.5% one-directional machine traffic, with a thin thread of real correspondence
running through it.

### The top offender is not what you'd guess

Gmail's API caps result counts at 201, so these are **frequency observations
from a 90-day sample, not exact totals** — get the real numbers with the search
queries at the end of this section. In that sample the densest sender was not a
retailer:

1. **`discover@services.discover.com`** — one "Transaction Alert" per purchase,
   with no floor. There are alerts in there for a $3.00 subway tap and a $4.75
   coffee. On several sampled days it fired 5+ times.
2. **`noreply@uber.com`** — **two** emails per single ride. A "charge summary"
   on completion, then a near-identical "thanks for riding" receipt roughly 11
   hours later. Every ride is double-counted.
3. Then the retail blasts — LoveShackFancy, EB Denim, Dolls Kill, Gilt, Grailed,
   ThredUp, TheRealReal, and ~20 more.

On sampled days these two produced more messages than every retailer combined,
and neither carries information you can't get from the Discover and Uber apps.
Measure them yourself before the big sweep:

```
in:inbox from:discover@services.discover.com
in:inbox from:noreply@uber.com
```

Gmail's UI shows a true count at the top right of the results.

### What's real, and getting buried

The same sample surfaced actual correspondence — this is what the noise is
hiding:

- `bbiern@sf.wish.org` — Betsy Biern, CEO of Make-A-Wish Greater Bay Area.
  Vendor coordination, often CC'ing `lbooth1@tulane.edu`.
- `betsyb1115@yahoo.com` — family threads to the Booth family addresses.
- `washsem@sfmc.american.edu` — American University Washington Semester Program,
  addressed "Dear Lucy," with event deadlines.
- `romneypilates@gmail.com` — studio schedule changes.

Several of these were **unread**.

## The fix

Two mechanisms, deliberately split:

| Scope | Mechanism | Why |
|---|---|---|
| The 72k backlog | Gmail filters, applied retroactively | Server-side, one pass, instant |
| New mail, daily | The agent (`CLAUDE.md`) | Judgment calls machines can't make |

Trying to clear the backlog through the API would mean ~72,000 individual
calls. Gmail's filter engine does it with one checkbox. Use the right tool.

## Importing the filters

`filters.xml` is generated from `config.yaml` — edit the config, not the XML.

```bash
python3 scripts/gen_filters.py
```

Then in Gmail:

1. **Settings** (gear) → **See all settings**
2. **Filters and Blocked Addresses**
3. **Import filters** at the bottom → choose `mail/filters.xml`
4. Review the parsed list — it will show all 8 rules before anything is created
5. Tick **"Apply new filters to existing conversations"** ← this is the step
   that clears the 72k
6. **Create filters**

### What the 8 rules do

| Rule | Senders | Action |
|---|---|---|
| Protect VIPs | Betsy (both), `*@tulane.edu`, `*@american.edu`, `*@sf.wish.org` | Always important, never spam. Runs first. |
| Transaction alerts | Discover | Archive, mark read, label `Receipts/Transactions` |
| Duplicate receipts | Uber | Archive, mark read, label `Receipts/Transactions` |
| Retail ×2 | 25 shops | Archive, mark read, label `Shopping & Promos` |
| Newsletters | 12 publications | Archive, **stay unread**, label `Newsletters & News` |
| Job alerts | LinkedIn, Idealist | Archive, **stay unread**, label `Internships & Career` |
| Transactional | Apple, Google, Wispr | Archive, mark read, label `Receipts/Transactions` |

Newsletters and job alerts deliberately stay **unread** so the label still
carries a badge — you'll see that something arrived without it sitting in your
inbox. Receipts get marked read because you only ever want those on search.

**Nothing is deleted.** Archive means out of the inbox, still in All Mail, still
searchable. Every rule is reversible: delete the filter, then search the label
and move it back.

### Before you tick the retroactive box

Spot-check that the rules catch what you expect and nothing you'd miss:

```
in:inbox from:{discover@services.discover.com noreply@uber.com}
in:inbox from:{bbiern@sf.wish.org betsyb1115@yahoo.com}
```

The first should be enormous and entirely disposable. The second should be
small and entirely worth keeping — and no filter touches it.

## The five empty labels

Gmail already has these, colored, with **zero messages** applied — a scaffold
someone set up and never used:

| Label | ID | Color |
|---|---|---|
| Important & Action Needed | `Label_7` | red |
| Internships & Career | `Label_3` | blue |
| Finance & Banking | `Label_4` | green |
| Newsletters & News | `Label_5` | purple |
| Shopping & Promos | `Label_6` | pink |

The generated filters reuse four of them rather than inventing a parallel
system. `Finance & Banking` is left free for actual bank mail — statements,
not the per-coffee alerts, which go to `Receipts/Transactions`.

## Unsubscribing beats filtering

Filters hide mail; they don't stop it. For anything in `noise.retail` you
genuinely don't want, unsubscribe instead — Gmail surfaces a one-click
**Unsubscribe** link next to the sender on most of these. Ten minutes of that
is worth more than any rule in this file.
