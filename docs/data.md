# Where data lives

Fischl uses two databases.

- **Firebase Realtime Database** holds settings and most feature data. BrawlKit uses the same Firebase database, and the bots that load `shared/` read and write the `shared/` paths in their own.
- **Postgres** (database `db`) holds the chat minigames, the website's expeditions, and every system listed under [Moved to Postgres](#moved-to-postgres).

## Firebase paths by system

| System | Top-level paths |
|---|---|
| Co-op | `Co-Op`, `Co-Op Sticky Panel`, `Co-Op-UID` |
| Reputation | `Global Reps`, `Global Reps System` |
| Partnership | `Partner` (BrawlKit reads this too) |
| Activity service | `Ian Activity` |
| Status and heartbeat | `Bot Status`, `Uptime` (the website reads both straight from the browser) |
| Boosters (`shared/`) | `Booster Role` |
| Tickets (`shared/`) | `Tickets`, `Ticket Panels`, `Ticket Blacklist`, `Ticket Closing Messages`, `Ticket Instructions`, `Ticket Snippets` |
| Welcome (`shared/`) | `Welcome`, `Welcome Content`, `WelcomeV2` |
| Embeds (`shared/`) | `Embed Templates` |
| Website | `Dashboard Users` |

## Moved to Postgres

Each system keeps its tables and queries in one store file. `scripts/firebase_to_postgres.py` copied the data in one go, checked every row against Firebase, and refuses to run again once the tables hold data. What it read is saved next to the old files, outside the repo, on the server. The Firebase paths were left as they were on the day of the move and are no longer read or written.

`/tag migrate` and `/vanity migrate` only switch a server on; they expect the settings Fischl Vanity saved to be in Postgres already. Anything Fischl Vanity writes to the old Firebase paths after the move is not picked up.

| System | Store | Tables | Old Firebase paths |
|---|---|---|---|
| Tag roles | `commands/Tag/tagStore.py` | `tag_enabled`, `tag_roles`, `tag_thanks`, `tag_thanks_cooldown` | `Tag Roles`, `Tag Thanks`, `Tag Thanks Message`, `Tag Thanks Cooldown`, and the file `commands/Tag/tagEnabledGuilds.py` |
| Vanity roles | `commands/Vanity/vanityStore.py` | `vanity_enabled`, `vanity_roles`, `vanity_thanks`, `vanity_thanks_cooldown` | `Vanity Roles`, `Vanity Thanks`, `Vanity Thanks Message`, `Vanity User`, and the file `commands/Vanity/enabledGuilds.py` |
| Sticky messages | `commands/Sticky/stickyStore.py` | `sticky_enabled`, `sticky_messages` | `Sticky Messages`, and the file `commands/Sticky/enabledChannels.py` |
| Topics | `commands/Utility/topicStore.py` | `topics` | `Topics` |
| Birthday | `commands/Birthday/birthdayStore.py` | `birthdays`, `birthday_servers` | `Birthday`, `Birthday System` (its `Server Name` field was never read and is not copied) |

## Rules for moving data

- A path another bot or the website reads stays where it is.
- Export first, copy with a script that stops when the tables already hold data, then compare every record.
- The old copy stays until Ian says to delete it.
