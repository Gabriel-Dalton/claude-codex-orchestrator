"""Detection and explicit configuration for other terminal agents."""

import time
from .base import Model, Provider, Usage, Window, number, timestamp, require_identifier

BINARIES = ("opencode", "aider", "cursor-agent", "gemini", "ollama")


class Generic(Provider):
    def models(self):
        configured = self.config.get("models")
        if configured is None:
            return None
        return [Model(require_identifier(row) if isinstance(row, str) else require_identifier(row["name"]),
                      None if isinstance(row, str) else row.get("efforts"),
                      "" if isinstance(row, str) else row.get("description", "")) for row in configured]

    def usage(self):
        data = self.config.get("usage", {})
        if self.name == "ollama" and self.installed():
            return Usage(observed_at=time.time(), unlimited=True)
        windows = [Window("window-" + str(i + 1), number(row.get("used_percent")),
                          number(row.get("window_minutes")), timestamp(row.get("resets_at")))
                   for i, row in enumerate(data.get("windows", []))]
        return Usage(windows, timestamp(data.get("observed_at")), data.get("limit_reached"))
