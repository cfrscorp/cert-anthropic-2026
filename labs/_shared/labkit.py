"""Shared helpers for CCAR-F lab tests.

The important one is `lab_module`: it imports the module under test from either
the learner's `starter/` directory (default) or the reference `solution/`
directory, controlled by the `LAB_TARGET` environment variable.

    # in labs/lab-03-.../tests/test_lab03.py
    from labkit import lab_module
    agent = lab_module(__file__, "agent_loop")   # -> starter/agent_loop.py by default
    agent.run(...)

Run the learner's work (default):      uv run pytest
Validate the reference solution:       LAB_TARGET=solution uv run pytest
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

__all__ = ["lab_module", "lab_root", "target_dir"]


def lab_root(test_file: str) -> Path:
    """Given a test file inside <lab>/tests/, return the lab root directory."""
    return Path(test_file).resolve().parent.parent


def target_dir(test_file: str) -> Path:
    """The starter/ or solution/ directory selected by LAB_TARGET (default starter)."""
    target = os.environ.get("LAB_TARGET", "starter")
    if target not in ("starter", "solution"):
        raise ValueError(f"LAB_TARGET must be 'starter' or 'solution', got {target!r}")
    return lab_root(test_file) / target


def _evict_foreign_siblings(directory: Path) -> None:
    """Drop sibling modules cached from a different lab's starter/solution dir.

    A "sibling" is any already-imported module whose file sits directly in some
    ``.../starter`` or ``.../solution`` directory other than ``directory``. These
    are the bare-name intra-lab modules that collide across labs; evicting them
    forces a fresh import from the current lab's dir. Uniquely-named modules
    (our ``labmod_*`` loads) and shared/site-packages modules are untouched.
    """
    directory_str = str(directory)
    for name, mod in list(sys.modules.items()):
        file = getattr(mod, "__file__", None)
        if not file:
            continue
        parent = os.path.dirname(os.path.abspath(file))
        if os.path.basename(parent) in ("starter", "solution") and parent != directory_str:
            del sys.modules[name]


def lab_module(test_file: str, module_name: str) -> ModuleType:
    """Import `module_name` from the active target dir (starter/ or solution/).

    Args:
        test_file: pass ``__file__`` from the test module.
        module_name: file stem without ``.py`` (e.g. "agent_loop").
    """
    directory = target_dir(test_file)
    path = directory / f"{module_name}.py"
    if not path.exists():
        raise FileNotFoundError(
            f"Cannot import '{module_name}': {path} does not exist. "
            f"(LAB_TARGET={os.environ.get('LAB_TARGET', 'starter')})"
        )
    # When the whole suite runs in one process, many labs define sibling modules
    # with the SAME bare name (schema.py, extract.py, agents.py, ...). Python
    # caches those under their bare name in sys.modules and searches sys.path in
    # order, so a later lab's `from schema import ...` can resolve to an EARLIER
    # lab's module. Prevent that: evict any sibling module cached from a
    # different lab's starter/solution dir, and force THIS lab's dir to the front
    # of sys.path so intra-lab bare-name imports resolve locally.
    _evict_foreign_siblings(directory)
    directory_str = str(directory)
    if directory_str in sys.path:
        sys.path.remove(directory_str)
    sys.path.insert(0, directory_str)
    unique = f"labmod_{directory.parent.name}_{os.environ.get('LAB_TARGET', 'starter')}_{module_name}"
    spec = importlib.util.spec_from_file_location(unique, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"Could not build import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique] = module
    spec.loader.exec_module(module)
    return module
