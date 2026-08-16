import importlib.util
from pathlib import Path

def test_config_defaults():
    spec = importlib.util.spec_from_file_location("agentd_config", "plugins/tamagotchai-agentd/config.py")
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.modules["agentd_config"] = mod
    spec.loader.exec_module(mod)
    cfg = mod.parse_args(["--backend", "file"])
    assert cfg.backend == "file"
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 7788
    assert cfg.stale_secs == 120
    assert cfg.poll_interval == 1

def test_config_env_overrides(monkeypatch):
    monkeypatch.setenv("TAMAGOTCHAI_PORT", "9999")
    monkeypatch.setenv("TAMAGOTCHAI_BACKEND", "webhook")
    monkeypatch.setenv("HERMES_WEBHOOK_SECRET", "s")
    spec = importlib.util.spec_from_file_location("agentd_config2", "plugins/tamagotchai-agentd/config.py")
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.modules["agentd_config2"] = mod
    spec.loader.exec_module(mod)
    cfg = mod.parse_args([])
    assert cfg.port == 9999
    assert cfg.backend == "webhook"
    assert cfg.secret == "s"