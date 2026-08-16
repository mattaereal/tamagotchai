# conftest.py
import sys
import importlib.util
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "plugins"))

# plugins/tamagotchai-agentd uses a hyphen in its directory name, which Python
# cannot import as the underscore module `tamagotchai_agentd` by itself. Load it
# explicitly and register under the underscore name so tests can import
# `tamagotchai_agentd.state` etc.
_pkg_dir = Path(__file__).parent / "plugins" / "tamagotchai-agentd"
if "tamagotchai_agentd" not in sys.modules and _pkg_dir.is_dir():
    spec = importlib.util.spec_from_file_location(
        "tamagotchai_agentd",
        _pkg_dir / "__init__.py",
        submodule_search_locations=[str(_pkg_dir)],
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tamagotchai_agentd"] = mod
    spec.loader.exec_module(mod)
