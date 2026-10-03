"""Small, privacy-safe provider interface. None means unknown."""

from dataclasses import dataclass, field
from datetime import datetime
import math
import re
import shutil
import subprocess


def number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    return None


def timestamp(value):
    if number(value) is not None:
        return float(value)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.timestamp() if parsed.tzinfo else None
        except ValueError:
            pass
    return None


def identifier(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._:-]+", value) else None


def require_identifier(value):
    if not identifier(value):
        raise ValueError("Model, effort and provider names must match ^[A-Za-z0-9._:-]+$")
    return value


@dataclass
class Model:
    name: str
    efforts: list[str] | None = None
    # Descriptions stay internal, since they can contain account information.
    description: str = ""


@dataclass
class Window:
    name: str
    used_percent: float | None
    window_minutes: float | None = None
    resets_at: float | None = None
    expected_percent: float | None = None
    ahead_of_pace: bool | None = None
    projected_exhaustion_at: float | None = None


@dataclass
class Usage:
    windows: list[Window] = field(default_factory=list)
    observed_at: float | None = None
    limit_reached: bool | None = None
    plan_type: str | None = None
    unlimited: bool = False


def run(command):
    """Never print subprocess output or exceptions containing private paths."""
    try:
        return subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None


class Provider:
    can_launch = False

    def __init__(self, name, config=None):
        self.name = require_identifier(name)
        self.config = config or {}

    def executable(self):
        return shutil.which(self.name)

    def installed(self):
        return self.executable() is not None

    def signed_in(self):
        return None

    def models(self):
        return None

    def usage(self):
        return Usage()

    def command(self, folder, model, effort):
        return None

    def read_screen(self, screen):
        return None
