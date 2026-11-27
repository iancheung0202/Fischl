# Contributing to Fischl

Thanks for wanting to help. I'm Ian, the creator of Fischl. The process is short.

## How a change gets in

1. Fork the repo and make your change in your fork.
2. Add tests for it.
3. Run `pytest` and `pre-commit run --all-files`. Both have to pass, and CI runs them again on the pull request.
4. Open a pull request against `main`. Tell me what changes for server owners or members and why.
5. I review it, merge it, deploy it and test it live. Only I have access to the server the bot runs on.

## Setting up

You don't need a bot token or any real data:

```bash
pip install -r requirements.txt pytest pytest-asyncio pre-commit
pytest
```

The tests swap Firebase for a tree that lives in memory (`tests/conftest.py`), so you can't break anyone's data by running them.

Tests of systems that keep their data in Postgres need an empty throwaway database. Point `TEST_DATABASE_URL` at one whose name ends in `_test` (it is wiped before every test), for example `postgresql://postgres:test@localhost:5432/fischl_test`. Without it those tests are skipped; CI always runs them.

## What I look for in a pull request

- **Nothing cut.** Tidy how something is written, but leave what it does alone: no removed features, renamed commands or changed messages, unless that is the point of the pull request.
- **Small and plain code.** Short functions with a one-line docstring. No dead code, leftover helpers or commented-out blocks.
- **One home for everything.** The map in [AGENTS.md](AGENTS.md#map-of-the-code) shows which folder holds what. Shared values are written once and imported.
- **Nothing slow on the hot paths.** The bot sees thousands of events a minute; [docs/performance.md](docs/performance.md) explains what to keep out of them.
- **Tests.** For a bug fix, write the test that fails without your fix.

The full list of rules is in [AGENTS.md](AGENTS.md).

## Secrets

Never commit a token, a key or a credentials file, and never paste one into a pull request, an issue or a chat. `assets/` and `web/config/` are ignored by git for this reason. If you think one got out, tell me straight away so I can replace it.
