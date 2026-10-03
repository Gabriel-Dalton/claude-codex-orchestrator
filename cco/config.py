"""Configuration with no account or repository-specific defaults."""

import os
from pathlib import Path
import tomllib
import sys
from .providers.base import require_identifier

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


def validate(cfg):
    for values in cfg["tiers"].values():
        for key in ("model", "effort", "provider"):
            if key in values:
                require_identifier(values[key])
    for provider, models in cfg.get("classes", {}).items():
        require_identifier(provider)
        for model, kind in models.items():
            require_identifier(model)
            if kind not in ("fast", "workhorse", "frontier"):
                raise ValueError("Model class must be fast, workhorse or frontier")
    for provider, values in cfg.get("providers", {}).items():
        require_identifier(provider)
        for effort in values.get("efforts", []):
            require_identifier(effort)
        for model in values.get("models", []):
            require_identifier(model if isinstance(model, str) else model["name"])
            if isinstance(model, dict):
                for effort in model.get("efforts", []):
                    require_identifier(effort)
    from .budget import thresholds
    thresholds(cfg.get("budget"))
    return cfg


def load(path=None):
    cfg = {"tiers": {k: dict(v) for k, v in DEFAULTS.items()}, "agent_command": COMMAND}
    explicit = path or os.environ.get("CCO_CONFIG")
    selected = Path(explicit).expanduser() if explicit else user_folder("config") / "cco.toml"
    if not explicit and (Path.cwd() / "cco.toml").is_file():
        print("Ignoring working-folder cco.toml; use --config <path> or CCO_CONFIG to trust it.", file=sys.stderr)
    if explicit or selected.is_file():
        with selected.open("rb") as stream:
            data = tomllib.load(stream)
        cfg["agent_command"] = data.get("agent_command", COMMAND)
        for tier, values in data.get("tiers", {}).items():
            if tier not in DEFAULTS or not isinstance(values, dict):
                raise ValueError("Invalid tier configuration")
            cfg["tiers"][tier].update(values)
        for key in ("providers", "classes", "budget"):
            cfg[key] = data.get(key, {})
    return validate(cfg)
