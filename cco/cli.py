"""Command line entry point."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

from .app import App
from .config import load
from .orca import Orca, OrcaError, OrcaGone, TerminalGone
from .state import State


def positive(value):
    result = float(value)
    if not 0 < result < float("inf"):
        raise argparse.ArgumentTypeError("must be a positive finite number")
    return result


def parser():
    p = argparse.ArgumentParser(prog="cco")
    commands = p.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor")
    doctor.add_argument("--start", action="store_true")
    launch = commands.add_parser("launch")
    launch.add_argument("--dir", required=True)
    launch.add_argument("--task", required=True)
    launch.add_argument("--tier", choices=("easy", "standard", "hard"), required=True)
    for name in ("model", "effort", "title"):
        launch.add_argument("--" + name)
    for name in ("force", "dry-run"):
        launch.add_argument("--" + name, action="store_true")
    listing = commands.add_parser("list")
    listing.add_argument("--all", action="store_true")
    wait = commands.add_parser("wait")
    wait.add_argument("ids", nargs="+")
    wait.add_argument("--done", required=True)
    wait.add_argument("--timeout", type=positive, default=30)
    wait.add_argument("--interval", type=positive, default=2)
    peek = commands.add_parser("peek")
    peek.add_argument("id")
    peek.add_argument("--lines", type=int, default=20)
    send = commands.add_parser("send")
    send.add_argument("id")
    send.add_argument("text")
    stop = commands.add_parser("stop")
    stop.add_argument("id", nargs="?")
    stop.add_argument("--all-mine", action="store_true")
    task = commands.add_parser("task").add_subparsers(dest="task_command", required=True)
    new = task.add_parser("new")
    new.add_argument("--kind", choices=("fix", "feature", "docs", "review"), required=True)
    new.add_argument("--out", required=True)
    return p


def main(argv=None):
    # Agent screens contain characters a Windows console code page cannot print.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = parser().parse_args(argv)
    try:
        cfg = load()
        if args.command == "task":
            # This local-only command remains useful without Orca installed.
            source = Path(__file__).parent / "templates" / (args.kind + ".md")
            if not source.exists():
                source = Path(__file__).parent.parent / "templates" / (args.kind + ".md")
            target = Path(args.out).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8") as stream:
                stream.write(source.read_text(encoding="utf-8"))
            print(f"Created {target}")
            return 0
        orca = Orca()
        app = App(orca, State(), cfg)
        if args.command == "doctor":
            print("orca: " + orca.command[0])
            print("codex: " + (shutil.which("codex") or "not found"))
            for tier, spec in cfg["tiers"].items():
                print(f"{tier}: {spec['model']} effort={spec['effort']}")
            try:
                terminals = orca.terminals()
            except OrcaGone:
                if not args.start:
                    raise
                orca.start()
                terminals = orca.terminals()
            print("Orca is running")
            groups = {}
            for terminal in terminals:
                groups.setdefault(terminal.get("worktreePath") or "(unknown folder)", []).append(terminal)
            for folder, group in sorted(groups.items()):
                print(folder)
                for terminal in group:
                    print("  " + terminal["handle"])
        elif args.command == "launch":
            app.launch(args.dir, args.task, args.tier, args.model, args.effort, args.title, args.force, args.dry_run)
        elif args.command == "list":
            app.listing(args.all)
        elif args.command == "wait":
            return app.wait(args.ids, args.done, args.timeout, args.interval)
        elif args.command == "peek":
            if args.lines < 1:
                raise ValueError("--lines must be positive")
            app.peek(args.id, args.lines)
        elif args.command == "send":
            app.send(args.id, args.text)
        elif args.command == "stop":
            if bool(args.id) == args.all_mine:
                raise ValueError("Choose one agent id or --all-mine")
            app.stop(args.id, args.all_mine)
        return 0
    except OrcaGone as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except TerminalGone as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except (OrcaError, ValueError, OSError, subprocess.TimeoutExpired, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted; agents remain recorded", file=sys.stderr)
        return 130
