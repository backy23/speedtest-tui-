"""
User configuration file support.

Reads/writes ``~/.speedtest-tui/config.toml`` (or ``.json`` fallback for
Python 3.9/3.10 where ``tomllib`` isn't in stdlib).

Supported keys::

    server = 12345           # preferred server ID
    plan = 100               # plan speed in Mbps
    connections = 4          # concurrent connections
    ping_count = 10
    download_duration = 10.0
    upload_duration = 10.0
    alert_below = 0.0        # alert threshold in Mbps
    csv_file = ""            # auto-append CSV path
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

_CONFIG_DIR = os.path.join(Path.home(), ".speedtest-tui")
_CONFIG_FILE = "config.json"


def _config_path() -> str:
    return os.path.join(_CONFIG_DIR, _CONFIG_FILE)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULTS: Dict[str, Any] = {
    "server": None,
    "plan": 0.0,
    "connections": 4,
    "ping_count": 10,
    "download_duration": 10.0,
    "upload_duration": 10.0,
    "alert_below": 0.0,
    "csv_file": "",
}


# ---------------------------------------------------------------------------
# Read / Write
# ---------------------------------------------------------------------------

def load_config() -> Dict[str, Any]:
    """Load config from disk, returning defaults for missing keys."""
    path = _config_path()
    config = dict(DEFAULTS)

    if not os.path.isfile(path):
        return config

    try:
        with open(path, encoding="utf-8") as fh:
            user = json.load(fh)
        if isinstance(user, dict):
            config.update(user)
    except (json.JSONDecodeError, IOError):
        pass  # corrupt file; use defaults

    return config


def save_config(config: Dict[str, Any]) -> str:
    """Write *config* to disk.  Returns the file path."""
    path = _config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2, ensure_ascii=False)

    return path


def get_config_value(key: str) -> Any:
    """Get a single config value."""
    return load_config().get(key, DEFAULTS.get(key))


def set_config_value(key: str, value: Any) -> str:
    """Set a single config value and persist.  Returns file path."""
    config = load_config()
    config[key] = value
    return save_config(config)


def config_path() -> str:
    """Return the config file path (for display purposes)."""
    return _config_path()
