# Task 01: build Claude Codex Orchestrator

Read `AGENTS.md` first. Build the whole tool described there. Work only in this repository.

## Learn the real command line before writing code

Orca is installed and running on this machine. Its command line is `orca` (on Windows it may be at `%LOCALAPPDATA%\Programs\orca\resources\bin\orca` and not on PATH). Run `orca --help` and the `--help` of `repo`, `worktree` and `terminal` and their subcommands, and `orca terminal list --json`, and write what you learn to `docs/orca-cli.md`: each command cco uses, its flags, and the JSON it returns with invented values. Known facts to confirm:

- `orca terminal create --worktree path:<dir> --title <t> --command "<cmd>" --json` returns a terminal handle. For a folder Orca does not know it fails with "Timed out waiting for terminal handle after creation".
- `orca terminal send --terminal <h> --text "<text>" --enter` types and submits. `orca terminal read --terminal <h> --screen` shows the screen; with `--json` the typed but unsent text is in a `draft` field.
- `orca terminal close --terminal <h>` kills one terminal.
- With Orca closed, commands print "Orca is not running. Run 'orca open' first."
- A Codex terminal that is working shows a line like `Working (1m 02s`, and when a turn ends a line like `Worked for 5m 21s`, then the empty prompt `Ask Codex to do anything`. The line under the prompt names the model, the effort and the folder.

**Live terminals on this machine belong to other work. You may list them and read nothing else. You may create exactly one terminal for testing, titled `cco-selftest`, running a plain shell command and no agent, and you must close it afterwards. Do not launch any Codex agent, and do not close or send to any other terminal.**

## Commands

Run as `python -m cco <command>`, with a `cco` console entry in `pyproject.toml`.

- `doctor`: finds `orca` and `codex`, says whether Orca is running and offers `--start` to run `orca open`, shows the tier table, and lists live terminals grouped by folder.
- `launch --dir <folder> --task <file> --tier easy|standard|hard [--model <id>] [--effort <level>] [--title <t>] [--force]`: does everything in points 1, 4, 5, 6 and 7 of `AGENTS.md`, records the agent in the state file, and prints its id, terminal handle, model and effort. `--dry-run` prints what it would do.
- `list`: every agent cco launched, with folder, tier, model, elapsed time and state: `working`, `idle`, `needs-input`, `gone`. `--all` adds terminals cco did not launch, marked as not its own.
- `wait <id> --done report:<path> | pr:<branch> | idle [--timeout <minutes>] [--interval <seconds>]`: blocks until the signal. Exit 0 done, 2 timed out, 3 Orca gone, 4 terminal gone. On exit prints the last lines of the agent's screen. Several ids may be given; it waits for all. `pr:` uses the `gh` command line if present and says so if it is not.
- `peek <id> [--lines N]`: the last lines of an agent's screen.
- `send <id> "<text>"`: a follow-up message, confirmed the same way as in `launch`.
- `stop <id> | --all-mine`: closes terminals cco launched, and only those.
- `task new --kind fix|feature|docs|review --out <path>`: writes a task file from a template.

## Configuration and state

- `cco.toml`, looked for in the current folder and then the user's config folder, with built-in defaults:
  - `easy`: `gpt-5.6-luna`, effort `medium`: one-file fixes, copy, alt text.
  - `standard`: `gpt-5.6-terra`, effort `medium`: ordinary code changes with tests.
  - `hard`: `gpt-6-astra`, effort `medium`: design work, changes that can alter a whole site, logic where a mistake is costly.
  - the agent command template, default `codex -m {model} -c model_reasoning_effort={effort}`, so another terminal agent can be swapped in.
- State lives in the user's state folder, never in the target repository.

## The skill

`skill/SKILL.md`, written for Claude Code as the orchestrator. Short and practical:

- when delegating is worth it and when it is not,
- how to write the task file: read the repository's own rules first, one job, limits, how to finish, what to report, what must not be touched,
- one agent per folder, each in its own git worktree when several work on one repository,
- always `doctor` or `list` before launching, and after any Orca restart,
- choose the tier for the job and tell the person which model each agent got,
- start `wait` as a background task so the session is told when the agent is done,
- never accept an agent's own report as proof: rerun the checks and look at the result,
- when the person is working with other sessions in the same repository, tell them which folders and branches are taken,
- stop agents that are no longer needed.

## Documents

- `README.md`: what it is in three sentences, a diagram in text of who does what, install, a five-minute walk through with an invented repository, the commands, the tier table, limits and known problems, and what has not been measured. No claims about cost or speed.
- `docs/lessons.md`: the seven failures in `AGENTS.md`, each as what happened, why, and what the tool does about it. Also: on Windows, running Codex without a real terminal can leave it read-only, which is why cco uses Orca terminals; and an Orca started as a child of a short-lived process can die with it.
- `LICENSE`: MIT.

## Tests

`python -m unittest` with a fake `orca` script covering: the duplicate refusal, the fallback for an unknown folder, the unsent draft retry, the trust prompt, each `wait` exit code, tier to model mapping, `stop` refusing a terminal it did not launch, and screen parsing for working, idle and needs-input, using screen text with invented content.

Then one live check with the single `cco-selftest` terminal: launch a plain shell command through the same code path with the agent command overridden, read it, and stop it.

## Done

All tests pass, the live check passes, and `python -m cco doctor` runs on this machine. Search the whole repository for anything that breaks the privacy rule in `AGENTS.md` before finishing. Write `tasks/01-build.report.md`: what was built, what in Orca's command line differed from the known facts above, what could not be tested, and what you would do next.
