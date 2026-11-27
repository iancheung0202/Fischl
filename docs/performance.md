# Performance notes

The bot shares a small server with other software, so idle cost matters. These are the things that keep it low, and why each one is there. Measure before and after if you change any of them.

## Presences are most of the traffic

About 98% of the events Discord sends are presence updates, from every server the bot is in. Only two things read them: vanity roles and the activity service in `utils/activity.py`.

- `cogs/presenceFilter.py` skips a presence before discord.py decodes it when the bot does not hold that member. discord.py would throw it away after decoding anyway, so listeners see the same events.
- The vanity handler looks its log channel up in the member's own server first. `client.get_channel` searches every server.

Anything added to `on_presence_update`, or to a listener that runs on every message, runs thousands of times a minute. Keep database calls and file checks out of those paths.

## The member cache is off

`fischl.py` starts with `MemberCacheFlags.none()` and `chunk_guilds_at_startup=False`. Turning the cache on would hold every member of every server in memory.

The cost is that discord.py drops member events for members it does not hold, so `on_member_update` does not fire for most servers. `commands/Tag/tagEvent.py` shows the way around it: it reads `GUILD_MEMBER_ADD` and `GUILD_MEMBER_UPDATE` straight from the connection, builds a `discord.Member` from the event, uses it and lets it go. A full scan of a server runs at startup, when its settings change, and once an hour as a safety net.

## Heavy libraries load on first use

pandas and matplotlib are imported inside the functions that draw graphs or read spreadsheets, not at the top of the file. That keeps tens of megabytes out of memory until someone runs one of those commands. Do the same for any other large library.

## Logs rotate

`cogs/logs.py` keeps `console_output.log` to 20 MB with three older files.

## These rely on discord.py internals

The presence filter and the tag handler wrap `bot._connection.parsers`, which is not public API. Check both, and their tests in `tests/test_tag.py`, when upgrading discord.py.
