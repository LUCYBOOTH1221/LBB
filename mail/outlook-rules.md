# Outlook cleanup

The Microsoft 365 connector is **read-only** — `outlook_email_search`,
`outlook_calendar_search`, `chat_message_search`. Even once it's authorized, the
agent can read your Tulane mail but cannot label, move, or archive anything in
it.

So Outlook cleanup is done with **Outlook Rules**, by you, once. The agent's job
there is reading and surfacing, not filing.

## Authorize the connector first

On claude.ai → **Settings → Connectors** → find **Microsoft 365** → connect with
your Tulane account. Then set `accounts.school_outlook.status` to `live` in
`config.yaml` and rebuild the dashboard.

If Tulane's IT has locked third-party app consent — common at universities —
this will fail with an admin-approval error. That's a policy decision on their
end, not something to work around. The dashboard will keep showing School as
"Not authorized," which is accurate.

## Rules to create

**File → Manage Rules & Alerts → New Rule**, or in Outlook on the web:
**Settings → Mail → Rules**.

Mirror the Gmail taxonomy so both mailboxes use the same vocabulary — the whole
point is one mental model across three accounts.

| # | Condition | Action |
|---|---|---|
| 1 | From anyone in Contacts, **or** subject contains `advisor`, `registrar`, `thesis` | Move to **Important & Action Needed**, mark high priority. Put this rule **first** and tick "stop processing more rules". |
| 2 | Sender address contains `noreply` or `no-reply` | Move to **Notifications**, mark read |
| 3 | Subject contains `[Canvas]` or sender contains `instructure` | Move to **School/Canvas** |
| 4 | From `*@tulane.edu` and body contains `due` or `deadline` | Flag for follow-up |
| 5 | Subject contains `unsubscribe`, or category is Bulk | Move to **Newsletters** |

Rule 1 running first with "stop processing" is what keeps a professor's mail
from being swept up by rule 2 or 5 — the same protect-the-humans-first ordering
the Gmail filters use.

## Clutter and Focused Inbox

Outlook's **Focused Inbox** is a built-in classifier that works reasonably well
once you train it. Right-click anything misfiled → **Move to Focused / Other**.
Fifteen corrections in the first week is worth more than another five rules.

Turn **Clutter** off if it's on — it competes with your rules and moves mail
somewhere you won't look.

## What lands on the dashboard

Once connected, the agent reads Outlook on each brief and merges results into
the same "Waiting on you" lane as Gmail, sorted by age rather than by account.
A message from a professor and one from a boss sit in one list — which is the
behavior you asked for and the reason the accounts aren't given separate panels.

Until then the School chip stays amber and no Outlook rows appear. The dashboard
does not guess.
