# Claude Codex Orchestrator

Claude Codex Orchestrator is a small command line tool and a Claude Code skill
for directing Codex agents in Orca terminals. Claude Code writes the brief and
checks the result while Codex works in an assigned folder. The `cco` command
records owned terminals, selects a configured model, and waits for an explicit
completion signal.

```text
Person
  |
  v
Claude Code: brief, choose tier, review and rerun checks
  |
  v
cco: discover, launch, confirm submission, wait, stop
  |
  v
Orca terminals: one assigned folder per Codex agent
  |
  v
Changed files + report: evidence for Claude Code to review
```

## Install

Use Python 3.11 or newer. The tool and its build backend use only the standard
library. Orca and Codex must already be installed for agent work. PR completion
also needs `gh`, authenticated for the target repository.

From this checkout, run `python -m cco --help`; no installation is needed.
To install the console command in your own environment, use
`python -m pip install --no-deps --no-build-isolation .`. This repository declares
no build or runtime dependencies. No packages were installed during development.
Copy `skill/SKILL.md` into your Claude Code skills directory as
`claude-codex-orchestrator/SKILL.md` to make the playbook available there.

## Five-minute walkthrough

These commands assume the console command is installed. With no installation,
run from this checkout and replace `cco` with `python -m cco`.

```sh
cco doctor
cco task new --kind fix --out ~/code/example-app/TASK.md
```

Edit `TASK.md`: name one bug, the limits, checks to run, and `TASK.report.md` as
the report. Make sure the target folder is registered in Orca or is a worktree
of a registered repository. Inspect existing terminals before launching:

```sh
cco list --all
cco launch --dir ~/code/example-app --task TASK.md --tier standard --dry-run
cco launch --dir ~/code/example-app --task TASK.md --tier standard
```

The launch prints an agent id, terminal handle, model, and effort. Substitute
that id for `AGENT_ID` below. Run the wait in Claude Code's background task
facility if it should notify that session when complete.

```sh
cco wait AGENT_ID --done report:TASK.report.md --timeout 30
cco peek AGENT_ID --lines 30
```

Read the report and diff, rerun the checks, and inspect the resulting behavior.
If further work is needed, send a short follow-up or point at a new task file.
Stop the terminal once the agent is no longer needed:

```sh
cco send AGENT_ID "Read FOLLOWUP.md and write FOLLOWUP.report.md."
cco stop AGENT_ID
```

## Commands

| Command | Purpose |
| --- | --- |
| `doctor [--start]` | Find Orca and Codex, show tiers, list terminals by folder; optionally start Orca. |
| `launch --dir FOLDER --task FILE --tier easy\|standard\|hard` | Launch and confirm the task prompt. |
| `launch ... [--model ID] [--effort LEVEL] [--title TITLE]` | Override tier settings or the terminal title. |
| `launch ... [--force] [--dry-run]` | Explicitly allow a duplicate folder or inspect the proposed command. |
| `list [--all]` | Show owned agents and their current state; optionally list foreign terminal metadata. |
| `wait ID [ID ...] --done SIGNAL [--timeout MINUTES] [--interval SECONDS]` | Wait for every selected agent. Defaults: 30 minutes, 2-second polling. |
| `peek ID [--lines N]` | Read the last N screen lines; default 20. |
| `send ID "TEXT"` | Send and verify a follow-up to a ready agent. |
| `stop ID` or `stop --all-mine` | Close only recorded, matching terminal incarnations. |
| `task new --kind fix\|feature\|docs\|review --out PATH` | Create a task template without overwriting an existing file. |

Signals are `report:PATH`, `pr:BRANCH`, or `idle`. Relative report paths resolve
inside each agent's target folder. Use a new report path for every task:
an already existing report satisfies the signal immediately. A PR signal means
an open PR exists for the branch, including one that predates this invocation.
An idle screen means the turn ended; none of these signals proves correctness.

Wait exits with 0 for completion, 2 for timeout, 3 for Orca unavailable, and 4
for a missing or replaced terminal. Other errors use 1. It prints the most
recent screen captured for each agent, or says the screen is unavailable.
Completed agents stay completed while a multi-agent wait finishes the others.
`list` states are `working`, `idle`, `needs-input`, and `gone`; unrecognized or
unavailable screens are conservatively `needs-input`.

## Tiers and configuration

| Tier | Default model | Effort | Jobs |
| --- | --- | --- | --- |
| easy | `gpt-5.6-luna` | medium | One-file fixes, copy, alt text. |
| standard | `gpt-5.6-terra` | medium | Ordinary code changes with tests. |
| hard | `gpt-6-astra` | medium | Design, site-wide changes, costly logic mistakes. |

These are the requested defaults, not a claim about availability or measured
quality. `cco.toml` in the current working folder takes precedence over the
user configuration at `%APPDATA%/cco/cco.toml` on Windows or
`${XDG_CONFIG_HOME:-~/.config}/cco/cco.toml` elsewhere. Missing values use the
built-in defaults. The checked-in file illustrates the full configuration.

The default `agent_command` is
`codex -m {model} -c model_reasoning_effort={effort}`. CCO appends `-C <folder>`
so fallback terminals still start in the requested directory. Include `{dir}`
in a custom command template to control directory placement yourself. Model
and effort values must be simple identifiers. Directory quoting assumes
PowerShell on Windows and a POSIX shell elsewhere. Configure the command
explicitly for a different shell. Configuration is executable local input;
review a repository's `cco.toml` before launching from it.

State is `agents.json` under `%LOCALAPPDATA%/cco` on Windows or
`${XDG_STATE_HOME:-~/.local/state}/cco` elsewhere. It never goes in the target
repository. It contains local paths, task paths, handles, and model selections;
do not publish it. Writes are atomic and mutations use a process lock. If a
process dies while holding the lock, verify no mutation is still running before
removing `mutation.lock` in that state folder.

## Limits and known problems

- Run discovery again after every Orca restart. A restored terminal still
  counts as a duplicate. `--force` permits another launch but grants no rights
  to read, send to, or close foreign terminals.
- Folder matching uses Orca metadata, saved target folders, and recognizable
  model footers in list previews. An unrelated terminal with no usable path
  cannot always be associated with its actual folder. Keep one agent per
  folder and use separate git worktrees for simultaneous changes.
- An unknown folder can make creation time out. CCO retries through the nearest
  registered ancestor or the registered main repository of a sibling worktree.
  If a new terminal appears after that failure, it refuses an ambiguous retry.
  A host that creates a terminal later than its timeout can still race discovery.
- Codex screen layouts can change. Missing screens, new approval dialogs, and
  unconfirmed submissions require inspection. Automatic trust acceptance is
  limited to a recognized numbered affirmative folder-trust option.
- A creation that returns no handle cannot safely be owned or closed. Inspect
  Orca before retrying. An agent that fails submission after getting a handle
  remains recorded and can be inspected or stopped.
- A changed terminal incarnation is treated as gone, even if its handle is
  reused. CCO does not adopt foreign terminals.
- Custom commands can change the launched program, but verified interactive
  submission and idle detection currently understand Codex screens only.
- `task new` is local and works without Orca. Other commands report when Orca
  is unavailable. `doctor --start` uses Orca's own app launcher.
- The permitted live shell test created and closed its terminal, but the screen
  was unavailable, so output verification did not pass. Real Codex launches,
  Orca shutdown/restart, and real PR creation were not exercised.

No cost savings, speed improvements, throughput, or comparative model quality
have been measured. The tests establish fixture behavior, not performance.

## Development

Run `python -m unittest`. Tests use a subprocess fake Orca and invented screen
content; they need neither Orca nor Codex. See [CLI observations](docs/orca-cli.md),
[lessons](docs/lessons.md), and the [build report](tasks/01-build.report.md).
