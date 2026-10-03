"""Operations over owned agents. No terminal protocol details live here."""

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import time
import uuid

from . import codex
from .orca import OrcaError, OrcaGone, TerminalGone


def canonical(path):
    return os.path.normcase(str(Path(str(path).replace("\\", "/")).expanduser().resolve()))


def quote(value):
    if os.name == "nt":
        # The Windows shell Orca starts may be Command Prompt or PowerShell.
        # Double quotes work in both; single quotes reach the program literally in Command Prompt.
        text = str(value).replace("\\", "/")
        return '"' + text + '"' if re.search(r"[^A-Za-z0-9_./:\-]", text) else text
    return shlex.quote(str(value))


class App:
    def __init__(self, orca, state, config):
        self.orca, self.state, self.config = orca, state, config

    def owned(self, agent_id):
        record = self.state.read().get(agent_id)
        if not record:
            raise ValueError("Unknown agent id. Refusing to touch a terminal cco did not launch.")
        return record

    def live(self, record, terminals):
        if record.get("stopped"):
            return None
        for terminal in terminals:
            if terminal["handle"] == record["terminal"]:
                expected = record.get("incarnation")
                if expected and terminal.get("incarnationId") != expected:
                    return None
                return terminal
        return None

    def require_live(self, record):
        if not self.live(record, self.orca.terminals()):
            raise TerminalGone("Terminal is gone or its process incarnation changed")

    def nearest_repo(self, folder):
        repos = [Path(r["path"]).resolve() for r in self.orca.repos() if r.get("path")]
        ancestors = [p for p in repos if folder.is_relative_to(p)]
        if ancestors:
            return max(ancestors, key=lambda p: len(p.parts))
        # A sibling git worktree points back to the main repository's .git.
        try:
            p = subprocess.run(["git", "-C", str(folder), "rev-parse", "--git-common-dir"],
                               capture_output=True, text=True, timeout=10)
            common = (folder / p.stdout.strip()).resolve()
            if p.returncode == 0:
                for repo in repos:
                    if common == repo / ".git":
                        return repo
        except (OSError, subprocess.TimeoutExpired):
            pass
        raise ValueError("No registered ancestor or main repository found. Register the folder in Orca first.")

    def launch(self, folder, task, tier, model=None, effort=None, title=None,
               force=False, dry_run=False, *, submit_prompt=True):
        folder = Path(folder).expanduser().resolve()
        task = Path(task).expanduser()
        if not task.is_absolute():
            task = folder / task
        task = task.resolve()
        if not folder.is_dir() or not task.is_file() or not task.is_relative_to(folder):
            raise ValueError("Task must be an existing file inside the target folder")
        if any(c in str(task) for c in "\r\n"):
            raise ValueError("Task path must fit on one line")
        chosen = self.config["tiers"][tier]
        model, effort = model or chosen["model"], effort or chosen["effort"]
        if not all(isinstance(v, str) and re.fullmatch(r"[\w.-]+", v) for v in (model, effort)):
            raise ValueError("Model and effort must be simple identifiers")
        template = self.config["agent_command"]
        command = template.format(model=model, effort=effort, dir=quote(folder))
        if "{dir}" not in template:
            command += " -C " + quote(folder)
        prompt = f"Read {json.dumps(str(task), ensure_ascii=False)}, follow it, and write the requested report."
        with self.state.locked():
            terminals = self.orca.terminals()
            records = self.state.read()
            conflicts = set()
            for t in terminals:
                paths = [t.get("worktreePath"), codex.displayed_folder(t.get("preview", ""))]
                # Orphaned restored terminals may only expose a path in worktreeId.
                if "::" in t.get("worktreeId", ""):
                    paths.append(t["worktreeId"].split("::", 1)[1])
                if any(p and canonical(p) == canonical(folder) for p in paths):
                    conflicts.add(t["handle"])
            for record in records.values():
                if canonical(record["folder"]) == canonical(folder) and self.live(record, terminals):
                    conflicts.add(record["terminal"])
            if conflicts and not force:
                raise ValueError("A live terminal already exists for this folder. Use --force only to deliberately add another.")
            if dry_run:
                print(json.dumps({"folder": str(folder), "model": model, "effort": effort,
                                  "command": command, "prompt": prompt, "title": title or "cco-" + tier}, indent=2))
                return None
            try:
                terminal = self.orca.create(folder, title or "cco-" + tier, command)
            except OrcaError as exc:
                if "Timed out waiting for terminal handle after creation" not in str(exc):
                    raise
                # Never blindly duplicate a possibly successful creation.
                after = self.orca.terminals()
                if {t["handle"] for t in after} - {t["handle"] for t in terminals}:
                    raise ValueError("Creation was ambiguous and a new terminal appeared. Inspect list --all before retrying.") from exc
                parent = self.nearest_repo(folder)
                if parent == folder:
                    raise
                terminal = self.orca.create(parent, title or "cco-" + tier, command)
            agent_id = uuid.uuid4().hex[:12]
            record = {"terminal": terminal["handle"], "incarnation": terminal.get("incarnationId"),
                      "folder": str(folder), "task": str(task), "tier": tier, "model": model,
                      "effort": effort, "started": time.time(), "stopped": False}
            records[agent_id] = record
            self.state.save(records)
            print(f"{agent_id} {record['terminal']} model={model} effort={effort}", flush=True)
            if submit_prompt:
                codex.submit(self.orca, record["terminal"], prompt)
            return agent_id

    def listing(self, all_terminals=False):
        terminals = self.orca.terminals()
        owned = set()
        for agent_id, record in self.state.read().items():
            live = self.live(record, terminals)
            state = "gone"
            if live:
                owned.add(live["handle"])
                try:
                    state = codex.classify(self.orca.read(live["handle"]))
                except TerminalGone:
                    pass
            elapsed = max(0, int(time.time() - record["started"]))
            print(f"{agent_id} {state} {record['folder']} tier={record['tier']} model={record['model']} effort={record['effort']} elapsed={elapsed}s")
        if all_terminals:
            for terminal in terminals:
                if terminal["handle"] not in owned:
                    print(f"{terminal['handle']} not-owned {terminal.get('worktreePath') or '(unknown folder)'}")

    def peek(self, agent_id, lines=20):
        record = self.owned(agent_id)
        self.require_live(record)
        print("\n".join(self.orca.read(record["terminal"])["text"].splitlines()[-lines:]))

    def send(self, agent_id, text):
        with self.state.locked():
            record = self.owned(agent_id)
            self.require_live(record)
            codex.submit(self.orca, record["terminal"], text)
        print("Submission confirmed")

    def stop(self, agent_id=None, all_mine=False):
        with self.state.locked():
            records = self.state.read()
            selected = list(records) if all_mine else [agent_id]
            for item in selected:
                self.owned(item)
            terminals = self.orca.terminals()
            for item in selected:
                record = records[item]
                if self.live(record, terminals):
                    self.orca.close(record["terminal"])
                record["stopped"] = True
                self.state.save(records)
                print(f"{item} stopped")

    def wait(self, ids, done, timeout=30, interval=2):
        records = {i: self.owned(i) for i in ids}
        if done != "idle" and not (done.startswith("report:") or done.startswith("pr:")):
            raise ValueError("--done must be idle, report:<path>, or pr:<branch>")
        if done != "idle" and not done.split(":", 1)[1]:
            raise ValueError("Completion signal requires a path or branch")
        if done.startswith("pr:") and not shutil.which("gh"):
            raise ValueError("PR completion requires the gh command; it was not found")
        deadline = time.monotonic() + timeout * 60
        remaining, screens = set(records), {}
        code = 0
        try:
            while remaining:
                terminals = self.orca.terminals()
                for item in list(remaining):
                    record = records[item]
                    if not self.live(record, terminals):
                        raise TerminalGone(f"{item}: terminal is gone")
                    screen = self.orca.read(record["terminal"])
                    screens[item] = screen["text"]
                    if done == "idle":
                        finished = codex.classify(screen) == "idle"
                    elif done.startswith("report:"):
                        report = Path(done[7:]).expanduser()
                        if not report.is_absolute():
                            report = Path(record["folder"]) / report
                        finished = report.is_file()
                    else:
                        p = subprocess.run(["gh", "pr", "list", "--head", done[3:], "--state", "open",
                                            "--json", "number", "--limit", "1"], cwd=record["folder"],
                                           capture_output=True, text=True, timeout=30)
                        if p.returncode:
                            raise ValueError("gh PR check failed: " + p.stderr.strip())
                        finished = bool(json.loads(p.stdout))
                    if finished:
                        remaining.remove(item)
                        print(f"{item} done ({done})")
                if not remaining:
                    break
                if time.monotonic() >= deadline:
                    print("Timed out waiting for completion")
                    code = 2
                    break
                time.sleep(min(interval, max(0, deadline - time.monotonic())))
        except OrcaGone as exc:
            print(str(exc))
            code = 3
        except TerminalGone as exc:
            print(str(exc))
            code = 4
        finally:
            for item in records:
                print(f"{item} last screen:")
                print("\n".join(screens.get(item, "Screen unavailable").splitlines()[-20:]))
        return code
