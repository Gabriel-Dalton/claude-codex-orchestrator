"""Gather provider facts and emit only the public inventory schema."""

import json
import re
import time
from .budget import evaluate
from .providers.base import require_identifier
from .providers.codex import Codex
from .providers.claude import Claude
from .providers.generic import Generic, BINARIES

CLASSES = ("fast", "workhorse", "frontier")
KNOWN = {"gpt-5.6-luna": "fast", "gpt-5.6-terra": "workhorse",
         "gpt-5.6-sol": "workhorse", "gpt-6-astra": "frontier",
         "gpt-5.5": "workhorse", "haiku": "fast", "sonnet": "workhorse", "opus": "frontier"}


def model_class(provider, model, config):
    override = config.get("classes", {}).get(provider, {}).get(model.name)
    if override is not None:
        if override not in CLASSES:
            raise ValueError("Model class must be fast, workhorse or frontier")
        return override
    matches = set(re.findall(r"\b(frontier|workhorse|fast)\b", model.description, re.I))
    matches = {value.lower() for value in matches}
    if len(matches) == 1:
        return matches.pop()
    return KNOWN.get(model.name)


def adapters(config):
    providers = config.get("providers", {})
    return [Codex(providers.get("codex")), Claude(providers.get("claude")),
            *(Generic(name, providers.get(name)) for name in BINARIES)]


def collect(config, providers=None, *, usage=False, now=None):
    now = time.time() if now is None else now
    result = []
    for provider in adapters(config) if providers is None else providers:
        name = require_identifier(provider.name)
        installed = provider.installed()
        if usage:
            result.append({"provider": name, "installed": installed,
                           **evaluate(provider.usage(), config.get("budget"), now)})
            continue
        models = provider.models()
        rows = None
        if models is not None:
            rows = []
            for model in models:
                require_identifier(model.name)
                if model.efforts is not None:
                    for effort in model.efforts:
                        require_identifier(effort)
                kind = model_class(name, model, config)
                rows.append({"name": model.name, "class": kind, "efforts": model.efforts,
                             "usable": kind is not None})
        result.append({"provider": name, "installed": installed, "signed_in": provider.signed_in(),
                       "can_launch": provider.can_launch, "models": rows})
    return {"providers": result}


def render(data, *, usage=False, as_json=False):
    if as_json:
        print(json.dumps(data, indent=2, allow_nan=False))
        return
    if not usage:
        print("PROVIDER  INSTALLED  SIGNED-IN  MODEL  CLASS  EFFORTS  USABLE")
    def value(item):
        return "unknown" if item is None else str(item).lower() if isinstance(item, bool) else str(item)
    for row in data["providers"]:
        if usage:
            age = row["age_seconds"]
            print(f"{row['provider']}: {row['state']} age={value(round(age, 1) if age is not None else None)}s")
            if row["unlimited"]:
                print("  local models: no limit")
            for window in row["windows"]:
                print(f"  {window['name']}: used={value(window['used_percent'])}% reset-in={value(window['reset_in_seconds'])}s "
                      f"expected={value(window['expected_percent'])}% ahead-of-pace={value(window['ahead_of_pace'])} "
                      f"pace-delta={value(window['pace_delta_percent'])}% state={window['state']}")
        else:
            prefix = f"{row['provider']}  {value(row['installed'])}  {value(row['signed_in'])}"
            for model in row["models"] or [{"name": "unknown", "class": None, "efforts": None, "usable": False}]:
                print(f"{prefix}  {model['name']}  {value(model['class'])}  "
                      f"{','.join(model['efforts']) if model['efforts'] is not None else 'unknown'}  {value(model['usable'])}")
