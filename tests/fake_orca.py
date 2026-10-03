"""A subprocess fixture with invented terminal data. Never calls real Orca."""

import json
import os
from pathlib import Path
import sys

path = Path(os.environ["CCO_FAKE_STATE"])
data = json.loads(path.read_text(encoding="utf-8"))
args = sys.argv[1:]
data.setdefault("calls", []).append(args)


def value(flag, default=None):
    return args[args.index(flag) + 1] if flag in args else default


def finish(result=None, error=None):
    path.write_text(json.dumps(data), encoding="utf-8")
    print(json.dumps({"ok": error is None, "result": result, "error": error}))
    raise SystemExit(1 if error else 0)


if data.get("gone") and args[0] != "open":
    finish(error="Orca is not running. Run 'orca open' first.")
if args[0] == "open":
    data["gone"] = False
    finish({"ready": True})
if args[:2] == ["repo", "list"]:
    finish({"repos": [{"path": data["repo"]}]})
if args[:2] == ["terminal", "list"]:
    finish({"terminals": data.get("terminals", []), "truncated": data.get("truncated", False)})
if args[:2] == ["terminal", "create"]:
    if data.get("fallback") and value("--worktree") != "path:" + data["repo"]:
        if data.get("ambiguous"):
            data.setdefault("terminals", []).append({"handle": "term_uncertain"})
        finish(error="Timed out waiting for terminal handle after creation")
    terminal = {"handle": "term_owned", "incarnationId": "process_one",
                "worktreePath": value("--worktree")[5:], "preview": ""}
    data.setdefault("terminals", []).append(terminal)
    finish({"terminal": terminal})
if args[:2] == ["terminal", "read"]:
    if data.get("read_gone"):
        finish(error="Terminal not found")
    screen = data.get("screen", "\u203a Ask Codex to do anything")
    finish({"terminal": {"tail": screen.splitlines(), "draft": data.get("draft", ""),
                         "source": data.get("source", "screen")}})
if args[:2] == ["terminal", "send"]:
    text = value("--text")
    if data.get("stalled"):
        finish({"inputAccepted": True})
    if text == "1" and data.get("trust"):
        data["screen"] = "\u203a Ask Codex to do anything"
        finish({"inputAccepted": True})
    if data.get("retry") and text:
        data["draft"] = text
        finish(error="No turn start was observed")
    data["draft"] = ""
    data["screen"] = "Working (1m 02s)"
    finish({"inputAccepted": True})
if args[:2] == ["terminal", "close"]:
    data["terminals"] = [t for t in data.get("terminals", []) if t["handle"] != value("--terminal")]
    finish({"closed": True})
finish(error="Unsupported fake command")
