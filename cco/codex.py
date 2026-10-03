"""Codex screen interpretation and verified submission, isolated from the CLI."""

import re
import time

from .orca import OrcaError


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
    if screen.get("draft"):
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
        elif classify(before) == "working" or before.get("draft"):
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
