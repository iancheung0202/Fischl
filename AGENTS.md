# AGENTS.md

This is for AI agents working on Fischl, and for any person who wants the full picture before changing something. Please read it first. The [README](README.md) covers what the bot is, and [CONTRIBUTING.md](CONTRIBUTING.md) covers how a pull request gets merged.

I'm Ian. I own the bot, so "I" and "me" below mean me.

## What you're working on

Fischl is a public Discord bot in a few hundred servers: tickets, welcome messages, co-op requests, chat minigames, partnerships, birthdays, tag and vanity roles, sticky messages. It also has a website with a dashboard and profile pages.

A lot of it was written by hand before AI tools existed, and some by AI tools when they were still rough. The job now is cleanup: making the code easy to maintain and cheap to run while keeping everything it does. What server owners and members see is the product. The mess they can't see is what we're fixing.

## How I want you to work

1. Don't change what people see. Messages, embeds, role changes, command names and options, web pages and API output stay the same unless that is the task I gave you.
2. Check, don't guess. Read the whole system before you change it, and look up command names, IDs and numbers in the code before you use them or tell me about them. When you report back, say what you verified and what you couldn't.
3. Other bots load our code. BrawlKit, Custom-Bots and ServerCV load everything under `shared/` and BrawlKit uses the same Firebase database. A change under `shared/`, or to data those bots read, has to be tested with all of them.
4. Keep secrets secret. Never print, log, commit or paste a token, key or credentials file. They live in git-ignored files under `assets/` and `web/config/`.
5. Treat live data as real, because it is. Before moving data, export it, and compare every record afterwards. Leave the old copy in place until I say to delete it.
6. Clean up the server when you're done. Every patch, bundle, scratch script and backup you put there gets deleted once the deploy is finished.
7. Space restarts out. The bot is in hundreds of servers and is offline for about half a minute each time. Make sure a batch is right, restart once, read the log, and wait a few minutes before the next one.

## Rules for the code

1. Don't cut features. Reorganize, rename internals, simplify how something is written, but don't remove what it does.
2. Copy the pattern that's already there. Before you add something, find the closest cleaned-up thing and build yours the same way.
3. Give everything one home. Each system has its own folder. Write a value once and import it. If the same logic is needed twice, move it somewhere both can reach.
4. Keep it small and plain. Short functions, plain names, and a one-line docstring saying what the function does or gives back. Leave out comments that describe your edit. Delete dead code, unused helpers and commented-out blocks.
5. Don't block the bot. Firebase and `requests` calls are blocking; in a listener that runs on every message or presence they stall every server at once. Keep them out of hot paths, cache what rarely changes, and run the rest in a thread.
6. Keep the member cache off and the heavy libraries lazy. The bot starts with `MemberCacheFlags.none()`, and pandas and matplotlib are imported inside the functions that use them. Both are there to save memory; see [docs/performance.md](docs/performance.md).
7. Write tests with every change, and get the tests and pre-commit passing before you ask me to look.
8. One commit per system, named `refactor: [system name] code cleanup`.

## Running things

```bash
pip install -r requirements.txt pytest pytest-asyncio pre-commit
pytest                      # whole suite
pytest tests/test_tag.py    # one file
pre-commit run --all-files  # black, isort, file checks
```

Use Python 3.10. That's what CI and production run.

### Tests

`tests/conftest.py` puts a stand-in for `assets/secret.py` in place, so nothing needs a token. The `firebase` fixture swaps Firebase for a tree in memory, and `no_loops` stops background loops from starting so a test can run one round by hand. Tests never touch the real database.

The `pool` fixture gives a real Postgres pool on an empty database. It needs `TEST_DATABASE_URL` pointing at a throwaway database, which it wipes before every test; without it those tests are skipped. CI sets one up.

### How a deploy works

- Production runs in one Docker container (`docker compose up -d --build`). `start.sh` starts `fischl.py` and, beside it, `web/main.py` for the website.
- `docker compose restart` restarts both. To restart only the website, run `docker compose exec bot pkill -f "python main.py"`; `start.sh` starts it again.
- The image installs `requirements.lock`, which pins every package. `requirements.txt` lists only what the code imports; change both together and rebuild.
- Slash commands sync when the bot starts.
- After a restart, read `console_output.log` for `Failed to load` lines and make sure the bot connected. A file that fails to load does not stop the bot, so the log is the only place it shows.
- Anything that has to survive a restart belongs in a database. Memory is wiped.

I've left the server address, login and paths out of this file on purpose, since the repo is public.

## Map of the code

`fischl.py` starts the bot, connects Firebase and Postgres, loads every `.py` under `cogs/`, `commands/` and `shared/` as an extension and registers the views that have to keep working after a restart. Because every file gets loaded as an extension, each one ends with `async def setup(bot)`, even when it has nothing to set up.

| Folder | Holds |
|---|---|
| `cogs/` | Things the bot does for itself: logging, command sync, status and heartbeat, metrics, the message history service, the presence filter |
| `commands/Birthday` | Birthday settings, the daily wishes and their texts |
| `commands/CoOp` | Co-op request panels and the reputation system |
| `commands/Custom` | Features written for single servers |
| `commands/Events` | The chat minigames, Mora, shop, quests, milestones, profile cards |
| `commands/Help` | `/help` |
| `commands/Partnership` | Partner servers, panels and threads |
| `commands/Sticky` | Sticky messages |
| `commands/Tag` | Roles for members wearing a server tag |
| `commands/Utility` | Small commands: topics, colors, emotes, invite, text |
| `commands/Vanity` | Roles for members with the server's invite in their status |
| `shared/` | Tickets, welcome, boosters and embed tools, also loaded by the other bots |
| `utils/` | Small web services the bot runs, pagination, persistent views |
| `web/` | The website: dashboard, profile, ticket history, payments |

[docs/data.md](docs/data.md) lists where each system keeps its data.
