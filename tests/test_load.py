import importlib
import os

import pytest

from tests.conftest import ROOT


def extensions():
    """Every file the bot loads as an extension, as fischl.py finds them."""
    for directory in ("cogs", "commands", "shared"):
        for path, _, files in os.walk(os.path.join(ROOT, directory)):
            for name in sorted(files):
                if name.endswith(".py"):
                    full = os.path.relpath(os.path.join(path, name), ROOT)
                    yield full.replace(os.sep, ".")[:-3]


@pytest.mark.parametrize("extension", sorted(extensions()))
def test_extension_imports_and_has_setup(extension, firebase):
    module = importlib.import_module(extension)
    assert callable(getattr(module, "setup", None))
