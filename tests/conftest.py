import os
import sys
import types
from unittest.mock import patch

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

SECRETS = (
    "DISCORD_TOKEN DATABASE_PATH DATABASE_URL GROQ_API_KEY NTFY_LINK DATABASE_USER "
    "DATABASE_PASSWORD AUTH_USER AUTH_PASS API_KEY MSG_HISTORY_API_KEY"
).split()
secret = types.ModuleType("assets.secret")
for name in SECRETS:
    setattr(secret, name, "test")
sys.modules.setdefault("assets", types.ModuleType("assets"))
sys.modules.setdefault("assets.secret", secret)


class Ref:
    """One path in a Firebase tree kept in memory as {path: value}."""

    def __init__(self, tree, path):
        self.tree, self.path = tree, path.strip("/")

    @property
    def key(self):
        return self.path.rsplit("/", 1)[-1]

    def child(self, key):
        return Ref(self.tree, f"{self.path}/{key}")

    def get(self):
        prefix = self.path + "/"
        if self.path in self.tree:
            return self.tree[self.path]
        found = {}
        for path, value in self.tree.items():
            if path.startswith(prefix):
                node = found
                *parents, leaf = path[len(prefix) :].split("/")
                for parent in parents:
                    node = node.setdefault(parent, {})
                node[leaf] = value
        return found or None

    def set(self, value):
        self.delete()
        if isinstance(value, dict):
            for key, item in value.items():
                self.child(key).set(item)
        elif value is not None:
            self.tree[self.path] = value

    def update(self, value):
        for key, item in value.items():
            self.child(key).set(item)

    def delete(self):
        for path in list(self.tree):
            if path == self.path or path.startswith(self.path + "/"):
                del self.tree[path]

    def push(self, value=None):
        ref = self.child(f"key{len(self.tree)}")
        if value is not None:
            ref.set(value)
        return ref


@pytest.fixture
def firebase():
    """Swaps Firebase for a tree in memory; `firebase(path)` gives a Ref to it."""
    tree = {}
    with patch("firebase_admin.db.reference", lambda path="": Ref(tree, path)):
        yield lambda path="": Ref(tree, path)


@pytest.fixture
async def pool():
    """A pool on an empty throwaway Postgres database (TEST_DATABASE_URL)."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    assert url.endswith("_test"), "the database name must end in _test"
    import asyncpg

    pool = await asyncpg.create_pool(url, min_size=1, max_size=2)
    await pool.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
    yield pool
    await pool.close()


@pytest.fixture
def no_loops(monkeypatch):
    """Stops task loops from starting, so a test runs each one by hand."""
    from discord.ext import tasks

    monkeypatch.setattr(tasks.Loop, "start", lambda self, *args, **kwargs: None)
