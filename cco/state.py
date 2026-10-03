"""Atomic state and a cross-process mutation lock outside project folders."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import time

from .config import user_folder


class State:
    def __init__(self, folder=None):
        self.folder = Path(folder) if folder else user_folder("state")
        self.path = self.folder / "agents.json"

    def read(self):
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Invalid cco state file; refusing to replace it")
        return data

    def save(self, data):
        self.folder.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    @contextmanager
    def locked(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        lock = self.folder / "mutation.lock"
        deadline = time.monotonic() + 10
        while True:
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise ValueError("State is locked. If no cco mutation is running, remove mutation.lock from the state folder.")
                time.sleep(0.1)
        try:
            os.close(fd)
            yield
        finally:
            lock.unlink()
