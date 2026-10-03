"""Configuration with no account or repository-specific defaults."""

import os
from pathlib import Path
import tomllib

DEFAULTS = {
    "easy": {"model": "gpt-5.6-luna", "effort": "medium"},
    "standard": {"model": "gpt-5.6-terra", "effort": "medium"},
    "hard": {"model": "gpt-6-astra", "effort": "medium"},
}
COMMAND = "codex -m {model} -c model_reasoning_effort={effort}"


def user_folder(kind):
    if os.name == "nt":
        return Path(os.environ.get("APPDATA" if kind == "config" else "LOCALAPPDATA",
                                   Path.home() / "AppData" / "Local")) / "cco"
    return Path(os.environ.get("XDG_CONFIG_HOME" if kind == "config" else "XDG_STATE_HOME",
                               Path.home() / (".config" if kind == "config" else ".local/state"))) / "cco"


def load():
    cfg = {"tiers": {k: dict(v) for k, v in DEFAULTS.items()}, "agent_command": COMMAND}
    for path in (Path.cwd() / "cco.toml", user_folder("config") / "cco.toml"):
        if path.is_file():
            with path.open("rb") as stream:
                data = tomllib.load(stream)
            cfg["agent_command"] = data.get("agent_command", COMMAND)
            for tier, values in data.get("tiers", {}).items():
                if tier not in DEFAULTS or not isinstance(values, dict):
                    raise ValueError("Invalid tier configuration")
                cfg["tiers"][tier].update(values)
            break
    return cfg
