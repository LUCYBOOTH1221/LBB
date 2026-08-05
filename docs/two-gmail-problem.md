# The two-Gmail problem

You asked to clean up personal Gmail **and** work Gmail. There's a hard
constraint in the way, and it's worth understanding before you plan around it.

## The constraint

The Gmail connector authorizes **exactly one Google account**. Right now that
slot is held by `lbb122104@gmail.com`. There is no "add second account" —
connecting the work address would disconnect the personal one.

This is not a settings toggle or a limit that lifts on a paid plan. One
connector, one OAuth grant, one mailbox.

So of the three mailboxes you described:

| Mailbox | Reachable today |
|---|---|
| Personal Gmail | yes |
| Work Gmail | no — slot taken |
| School Outlook | no — different connector, not authorized |

## Four ways around it

### 1. Forward work → personal, filter on arrival  *(recommended)*

In work Gmail: **Settings → Forwarding → Add a forwarding address**, point it at
`lbb122104@gmail.com`, and choose **keep a copy in the inbox**.

Then one filter on the personal side catches everything that arrives that way:

```
from:(*@yourworkdomain.com) OR deliveredto:(your.work@gmail.com)
  → label Work/Marketing, never mark spam, always important
```

- **Pro:** one dashboard, one triage pass, immediate.
- **Con:** work mail physically lives in your personal account. If the job has
  any confidentiality expectation, check before doing this — this is the kind
  of thing that's fine at most jobs and a fireable offense at a few.
- **Reply carefully:** replies would go out from the personal address unless you
  add the work address as a "Send mail as" alias. Do that at the same time.

### 2. Swap the connector when you switch contexts

Disconnect and reconnect between personal and work. Free, no data mixing.
Genuinely annoying to do more than once a week, and the agent loses continuity
each time.

### 3. Google Workspace delegation

If the work account is Workspace (not a plain `@gmail.com`), the admin can
**delegate** it to your personal address. Delegated mail appears in one
interface without credential sharing, and the org keeps control.

- **Pro:** the clean answer, IT-sanctioned.
- **Con:** requires an admin to act, and delegated mail is not always visible
  to API connectors — verify before depending on it.

### 4. Wait for a multi-account connector

Superhuman Mail (in the connector directory, not currently installed) covers
both Gmail and Outlook and may handle multiple accounts. Unverified — worth ten
minutes of checking if the above all feel bad.

## Recommendation

Do **#1** if the marketing job has no confidentiality constraint — it's the only
option that gets you the single synced view you actually asked for, today.

Ask the boss first. "Can I forward work mail to my personal account so I don't
miss anything?" is a normal question with a fast answer, and a much better
outcome than discovering the policy afterwards.

If the answer is no, do **#3** and accept a few days of setup.
