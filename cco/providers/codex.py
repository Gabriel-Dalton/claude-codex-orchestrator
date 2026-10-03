"""Codex screen interpretation and verified submission, isolated from the CLI."""

import re
import time
import json
import os
from pathlib import Path

from .base import Model, Provider, Usage, Window, number, run, timestamp, require_identifier

from ..orca import OrcaError


def draft_text(screen):
    draft = (screen.get("draft") or "").strip()
    # Orca can expose the empty composer's visible placeholder as draft text.
    if draft.lstrip("\u203a> ").strip() == "Ask Codex to do anything":
        return ""
    return draft


def queue(orca, handle, text):
    """Queue once; a running turn need not produce a new turn-start receipt."""
    try:
        orca.send(handle, text)
        return True
    except OrcaError as exc:
        if "no turn start" not in str(exc).lower():
            raise
    screen = orca.read(handle)
    if draft_text(screen) == text.strip():
        try:
            orca.send(handle)
        except OrcaError as exc:
            if "no turn start" not in str(exc).lower():
                raise
        screen = orca.read(handle)
    return not draft_text(screen) and classify(screen) in ("working", "idle")


def shell_prompt(screen):
    if screen.get("source") == "screen-unavailable":
        return False
    lines = screen.get("text", "").rstrip().splitlines()
    return bool(lines and re.fullmatch(
        r"(?:PS\s+)?[A-Za-z]:[\\/].*>\s*|(?:[^\s]+@[^\s]+:)?[~/][^\n]*[$#]\s*", lines[-1]))


def classify(screen):
    if screen.get("source") == "screen-unavailable":
        return "needs-input"
    text = screen["text"]
    signals = []
    patterns = {
        "working": r"Working\s*\(|esc to interrupt|Waiting for background",
        "idle": r"Worked for[^\n]*|[›>]\s*Ask Codex to do anything",
        "needs-input": r"Do you trust|trust this folder|Would you like to|Allow .+\?|approve|Select an option",
    }
    for state, pattern in patterns.items():
        signals.extend((m.start(), state) for m in re.finditer(pattern, text, re.I))
    if draft_text(screen):
        return "needs-input"
    # The footer placeholder can remain visible while work is in progress.
    working = list(re.finditer(patterns["working"], text, re.I))
    ended = list(re.finditer(r"Worked for", text, re.I))
    if working and (not ended or working[-1].start() > ended[-1].start()):
        requests = [pos for pos, state in signals if state == "needs-input"]
        if not requests or max(requests) < working[-1].start():
            return "working"
    return max(signals)[1] if signals else "needs-input"


def displayed_folder(preview):
    matches = re.findall(r"gpt-[\w.-]+\s+\w+\s*[·•]\s*([^\n·]+)", preview)
    return matches[-1].strip() if matches else None


def trust(screen):
    return bool(re.search(r"Do you trust|trust this folder", screen["text"], re.I))


def submit(orca, handle, prompt, timeout=20, interval=0.25):
    deadline = time.monotonic() + timeout
    accepted_trust = False
    while True:
        before = orca.read(handle)
        if shell_prompt(before):
            raise ValueError("Agent program exited back to a shell prompt; inspect with peek")
        if trust(before):
            if accepted_trust:
                raise ValueError("Folder trust prompt did not clear")
            # Select the numbered affirmative option, not an arbitrary approval.
            if not re.search(r"1[.)]\s*(?:Yes|I trust)", before["text"], re.I):
                raise ValueError("Unrecognized trust prompt; inspect with peek")
            orca.send(handle, "1")
            accepted_trust = True
        elif classify(before) == "idle":
            break
        elif classify(before) == "working" or draft_text(before):
            raise ValueError("Agent is already working or has a draft; inspect with peek")
        if time.monotonic() >= deadline:
            raise ValueError("Agent prompt is not ready; inspect with peek")
        time.sleep(interval)
    try:
        orca.send(handle, prompt)
    except OrcaError as exc:
        if "no turn start" not in str(exc).lower():
            raise
    retried = False
    while True:
        screen = orca.read(handle)
        if shell_prompt(screen):
            raise ValueError("Agent program exited back to a shell prompt; inspect with peek")
        if classify(screen) == "working":
            return
        # A quick completed turn is evidence only if the rendered frame changed.
        if (screen["text"] != before["text"] and "Worked for" in screen["text"]
                and classify(screen) == "idle"):
            return
        if screen.get("draft", "").strip() == prompt.strip() and not retried:
            orca.send(handle)
            retried = True
        if time.monotonic() >= deadline:
            raise ValueError("Submission was not confirmed; agent remains recorded. Inspect with peek before sending again.")
        time.sleep(interval)


class Codex(Provider):
    can_launch = True

    def __init__(self, config=None, home=None):
        super().__init__("codex", config)
        self.home = Path(home or os.environ.get("CODEX_HOME", Path.home() / ".codex"))

    def executable(self):
        found = super().executable()
        if found:
            return found
        for path in (Path.home() / ".local/bin/codex", Path.home() / ".local/bin/codex.exe",
                     Path(os.environ.get("APPDATA", Path.home())) / "npm/codex.cmd"):
            if path.is_file():
                return str(path)
        return None

    def signed_in(self):
        executable = self.executable()
        result = run([executable, "login", "status"]) if executable else None
        if result is None:
            return None
        text = (result.stdout + result.stderr).lower()
        if "not logged in" in text:
            return False
        return True if result.returncode == 0 and "logged in" in text else None

    def models(self):
        try:
            data = json.loads((self.home / "models_cache.json").read_text(encoding="utf-8"))
            models = []
            for row in data["models"]:
                name = require_identifier(row["slug"])
                levels = row.get("supported_reasoning_levels")
                efforts = [require_identifier(level["effort"]) for level in levels] if isinstance(levels, list) else None
                models.append(Model(name, efforts, row.get("description", "")))
            return models
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return None

    def usage(self):
        try:
            paths = list((self.home / "sessions").rglob("rollout-*.jsonl"))
            if not paths:
                return Usage()
            latest = max(paths, key=lambda p: p.stat().st_mtime)
            reading = Usage()
            with latest.open(encoding="utf-8") as stream:
                for line in stream:
                    try:
                        row = json.loads(line)
                        payload = row.get("payload", {})
                        limits = payload.get("rate_limits") if isinstance(payload, dict) else None
                        if not isinstance(limits, dict):
                            continue
                        windows = []
                        for name in ("primary", "secondary"):
                            window = limits.get(name)
                            if isinstance(window, dict):
                                windows.append(Window(name, number(window.get("used_percent")),
                                                      number(window.get("window_minutes")), timestamp(window.get("resets_at"))))
                        plan = limits.get("plan_type")
                        if plan not in ("free", "plus", "pro", "team", "business", "enterprise", "edu"):
                            plan = None
                        reached = limits.get("rate_limit_reached_type")
                        reading = Usage(windows, timestamp(row.get("timestamp")),
                                        reached is not None and reached != "none", plan)
                    except (ValueError, TypeError, AttributeError):
                        continue
            return reading
        except OSError:
            return Usage()

    def command(self, folder, model, effort, *, template=None, quote=None):
        if quote is None:
            from ..app import quote
        from ..config import COMMAND
        require_identifier(model)
        require_identifier(effort)
        template = COMMAND if template is None else template
        command = template.format(model=model, effort=effort, dir=quote(folder))
        return command if "{dir}" in template else command + " -C " + quote(folder)

    def read_screen(self, screen):
        return classify(screen)
