# Where data lives

Fischl uses two databases.

- **Firebase Realtime Database** holds settings and most feature data. BrawlKit uses the same Firebase database, and the bots that load `shared/` read and write the `shared/` paths in their own.
- **Postgres** (database `db`) holds the chat minigames and the website's expeditions.

## Firebase paths by system

| System | Top-level paths |
|---|---|
| Birthday | `Birthday`, `Birthday System` |
| Co-op | `Co-Op`, `Co-Op Sticky Panel`, `Co-Op-UID` |
| Reputation | `Global Reps`, `Global Reps System` |
| Partnership | `Partner` (BrawlKit reads this too) |
| Sticky | `Sticky Messages` |
| Tag roles | `Tag Roles`, `Tag Thanks`, `Tag Thanks Cooldown`, `Tag Thanks Message` |
| Topics | `Topics` |
| Vanity roles | `Vanity Roles`, `Vanity Thanks`, `Vanity Thanks Message`, `Vanity User` |
| Activity service | `Ian Activity` |
| Status and heartbeat | `Bot Status`, `Uptime` (the website reads both straight from the browser) |
| Boosters (`shared/`) | `Booster Role` |
| Tickets (`shared/`) | `Tickets`, `Ticket Panels`, `Ticket Blacklist`, `Ticket Closing Messages`, `Ticket Instructions`, `Ticket Snippets` |
| Welcome (`shared/`) | `Welcome`, `Welcome Content`, `WelcomeV2` |
| Embeds (`shared/`) | `Embed Templates` |
| Website | `Dashboard Users` |

## Rules for moving data

- A path another bot or the website reads stays where it is.
- Export first, copy with a script that can be run again, then compare every record.
- The old copy stays until Ian says to delete it.
