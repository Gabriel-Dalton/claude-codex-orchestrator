"""The only module that speaks Orca's command line."""

import json
import os
from pathlib import Path
import shutil
import subprocess


class OrcaError(RuntimeError):
    pass


class OrcaGone(OrcaError):
    pass


class TerminalGone(OrcaError):
    pass


def find_orca():
    found = shutil.which("orca")
    if found:
        return found
    if os.name == "nt":
        candidate = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/orca/resources/bin/orca.exe"
        if candidate.is_file():
            return str(candidate)
    raise OrcaGone("Orca command not found. Install Orca or add it to PATH.")


class Orca:
    def __init__(self, command=None):
        self.command = command or [find_orca()]

    def call(self, *args):
        try:
            p = subprocess.run([*self.command, *args, "--json"], capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=45)
        except subprocess.TimeoutExpired as exc:
            raise OrcaError("Orca command timed out; its outcome is unknown. List terminals before retrying.") from exc
        try:
            data = json.loads(p.stdout)
        except ValueError:
            data = {}
        if p.returncode or data.get("ok") is False:
            message = p.stderr.strip() or p.stdout.strip() or "Orca command failed"
            lower = message.lower()
            if "not running" in lower or "econnrefused" in lower or "runtime_unavailable" in lower:
                raise OrcaGone("Orca is not running. Run 'orca open' first.")
            if "terminal" in lower and any(x in lower for x in ("not found", "no longer", "unknown terminal")):
                raise TerminalGone(message)
            raise OrcaError(message)
        if not data:
            raise OrcaError("Orca returned no valid JSON")
        return data.get("result", data)

    def terminals(self):
        data = self.call("terminal", "list", "--limit", "100000")
        if data.get("truncated") or data.get("hostScope", {}).get("omittedHostIds"):
            raise OrcaError("Terminal list is incomplete; refusing to assume a folder is free")
        return data["terminals"]

    def repos(self):
        return self.call("repo", "list")["repos"]

    def create(self, folder, title, command):
        data = self.call("terminal", "create", "--worktree", f"path:{folder}",
                         "--title", title, "--command", command)
        terminal = data.get("terminal", data)
        if not terminal.get("handle"):
            raise OrcaError("Creation returned no terminal handle; inspect list before retrying")
        return terminal

    def read(self, handle):
        data = self.call("terminal", "read", "--terminal", handle, "--screen")
        data = data.get("terminal", data)
        tail = data.get("tail", "")
        if isinstance(tail, list):
            tail = "\n".join(tail)
        return {"text": tail, "draft": data.get("draft", ""), "source": data.get("source", "screen")}

    def send(self, handle, text=None):
        args = ["terminal", "send", "--terminal", handle]
        if text is not None:
            args += ["--text", text]
        return self.call(*args, "--enter")

    def close(self, handle):
        return self.call("terminal", "close", "--terminal", handle)

    def start(self):
        # Orca's launcher hands the app off and waits only for runtime readiness.
        return self.call("open")
