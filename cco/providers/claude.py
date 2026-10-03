"""Claude inventory and account-switcher usage, without account identifiers."""

import json
import shutil
import time
from .base import Model, Usage, Window, number, run, timestamp
from .generic import Generic


class Claude(Generic):
    def __init__(self, config=None):
        super().__init__("claude", config)

    def signed_in(self):
        executable = self.executable()
        result = run([executable, "auth", "status", "--json"]) if executable else None
        if result:
            try:
                value = json.loads(result.stdout).get("loggedIn")
                return value if isinstance(value, bool) else None
            except (ValueError, AttributeError):
                pass
        return None

    def models(self):
        configured = super().models()
        if configured is not None:
            return configured
        # Efforts remain unknown until explicitly configured.
        return [Model(name, self.config.get("efforts")) for name in ("fable", "opus", "sonnet", "haiku")]

    def usage(self):
        executable = shutil.which("cswap")
        result = run([executable, "list", "--json"]) if executable else None
        if result is None or result.returncode:
            return Usage()
        try:
            data = json.loads(result.stdout)
            accounts = data.get("accounts", [])
            active = [row for row in accounts if row.get("active") is True]
            if not active and data.get("activeAccountNumber") is not None:
                active = [row for row in accounts if row.get("number") == data["activeAccountNumber"]]
            if len(active) != 1:
                return Usage()
            account = active[0]
            windows = []
            for name, minutes in (("fiveHour", 300), ("sevenDay", 10080)):
                row = (account.get("usage") or {}).get(name)
                if isinstance(row, dict):
                    ahead = row.get("aheadOfPace")
                    windows.append(Window(name, number(row.get("pct")), minutes,
                                          timestamp(row.get("resetsAt")), number(row.get("expectedPct")),
                                          ahead if isinstance(ahead, bool) else None,
                                          timestamp(row.get("projectedExhaustionAt"))))
            observed = timestamp(account.get("usageFetchedAt"))
            age = number(account.get("usageAgeSeconds"))
            if observed is None and age is not None and age >= 0:
                observed = time.time() - age
            reached = account.get("limitReached")
            return Usage(windows, observed, reached if isinstance(reached, bool) else None)
        except (ValueError, TypeError, AttributeError, KeyError):
            return Usage()
