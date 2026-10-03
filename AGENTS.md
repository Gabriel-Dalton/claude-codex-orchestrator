# Claude Codex Orchestrator

A small command line tool and a Claude Code skill that let one Claude Code session direct several Codex agents running in Orca terminals: launch them, know which model each one has, know when each is done, and stop them. Claude Code briefs and checks; Codex does the work.

This repository is public. Nothing private goes in it.

## Rules that do not bend

- No real people, clients, companies, repositories, email addresses, account names or local user paths anywhere: code, tests, docs, examples, commit messages. Examples use `~/code/example-app`, `example.com` and invented names.
- No secrets, tokens or usage data from a real account.
- Python 3.11 or newer, standard library only. No dependencies, no package installs.
- Never close, send to or otherwise touch an Orca terminal the tool did not launch itself, unless the person passes an explicit flag naming it.
- Do not commit or push. The reviewer does that.

## What the tool must get right

These come from real failures. Each has a test.

1. **No duplicates.** After Orca restarts it restores old terminals, and they keep working. Launching again gives two agents on one job. `launch` lists live terminals first and refuses when one already exists for that folder.
2. **Done is detected, not assumed.** Orca does not tell the caller when a Codex turn ends. `wait` watches for a chosen signal: a report file appearing, a pull request opening for a branch, or the terminal going idle. It also ends, with a different exit code, when Orca is gone or the time runs out.
3. **Orca can die.** Every command says so plainly when Orca is not running. `doctor` can start it with `orca open`, which returns at once and leaves the app up.
4. **Folders Orca does not know.** A git worktree Orca has not registered makes `terminal create` time out. `launch` falls back to the nearest registered repository and starts `codex -C <folder>`.
5. **The prompt may not have been submitted.** `terminal send --enter` sometimes reports that no turn start was observed. `launch` reads the screen afterwards and confirms the agent is working; if the text is still sitting in the draft it presses Enter once more. A trust prompt for a new folder is accepted first.
6. **The model fits the job.** Three tiers map to a model and an effort in one config file. `launch` takes a tier and prints the model it chose.
7. **One short prompt, one task file.** Long instructions live in a task file in the target folder. The prompt sent to the agent is one line that points at it.

## Layout

- `cco/`: the package. `orca.py` is the only module that knows Orca's command line; `codex.py` the only one that knows Codex's screen; everything else goes through them.
- `tests/`: `unittest`, run with `python -m unittest`. A fake `orca` script stands in for the real one, so the tests need neither Orca nor Codex.
- `skill/SKILL.md`: the playbook for Claude Code.
- `templates/`: task file templates.
- `docs/`: `lessons.md` and `orca-cli.md`.
- `tasks/`: task files for agents working on this repository. Each task writes a short report next to itself.

## Writing

Plain sentences. No em dashes. No sales language and no claims about savings that have not been measured.
