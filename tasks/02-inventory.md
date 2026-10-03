# Task 02: providers, inventory and usage

Read `AGENTS.md` and `docs/routing.md` first. `docs/routing.md` is the specification; this task builds sections 1, 2 and 3 of its Logic. Do not start until `tasks/01-build.report.md` exists. Nothing in this task changes how agents are launched.

## Build

1. `cco/providers/base.py`: the adapter interface. Every adapter answers: is it installed, is it signed in, which models, which effort levels, how much usage is left, what command starts it in a folder with a model and an effort, and how to read its screen. Any answer may be "unknown". Nothing guesses.
2. `cco/providers/codex.py`: move the Codex specific code from the first build behind the interface. Add:
   - models from `models_cache.json` in the Codex home folder (`models[].slug`, the supported effort levels, the description),
   - usage from the newest `rollout-*.jsonl` under `sessions/` in the Codex home folder, field `rate_limits` (`primary` and `secondary` windows with `used_percent`, `window_minutes`, `resets_at`; `plan_type`; `rate_limit_reached_type`), with the age of the reading.
   Look at the real files on this machine to confirm the shapes, then write invented fixtures. Never copy a real file into the repository.
3. `cco/providers/claude.py`: Claude Code. Models and efforts from config, default models `fable`, `opus`, `sonnet`, `haiku`. Usage from `cswap list --json` when that command exists (fields `usage.fiveHour.pct`, `usage.sevenDay.pct`, `resetsAt`, `expectedPct`, `aheadOfPace`, `projectedExhaustionAt` on the active account), otherwise unknown. Launching and screen reading for Claude Code are not part of this task; the adapter says it cannot launch yet.
4. `cco/providers/generic.py`: detection for other terminal agents by binary name (`opencode`, `aider`, `cursor-agent`, `gemini`, `ollama`), listed in the inventory as installed or not, with models and usage unknown unless set in config.
5. `cco/inventory.py`: gathers the adapters into one picture. `cco/budget.py`: turns each provider's windows into one state, `ok`, `tight`, `critical`, `exhausted` or `unknown`, exactly as section 3 defines them, with thresholds read from `cco.toml`.
6. Class mapping as section 2 defines it: override in `cco.toml`, then the provider's description, then a built in table. A model with no class is listed and marked unusable.
7. Commands: `cco inventory` (providers, sign in, models with class and efforts) and `cco usage` (each window: percent used, time to reset, pace, state, age of the reading). Both take `--json`.

## Privacy

Output and logs never contain an account name, email address or organisation name, even though the source files do. There is a test for this that feeds a fixture containing an invented email and asserts it does not appear in any output.

## Tests

Invented fixtures for the Codex model list, a rollout rate limit record and the account switcher JSON. Cover: each budget state, both Claude windows with the worse one governing, a stale reading becoming `unknown`, a machine with only one provider, a machine with none, and the class mapping order. `python -m unittest` must pass with no agent tools installed.

## Done

All tests pass. On this machine `python -m cco inventory` lists Codex with its models and `python -m cco usage` shows a reading for Codex. Run the privacy search from `AGENTS.md`. Write `tasks/02-inventory.report.md`: what was built, where the real files differed from what this task says, and what stayed unknown.

## Two fixes made by the reviewer after the first build, to cover with tests

Using the tool for real on Windows found two faults that the fake did not: the folder was quoted with single quotes, which Command Prompt passes through literally, so the agent failed to start; and `peek` crashed printing screen characters the console code page lacks. Both are fixed in `cco/app.py` (`quote`) and `cco/cli.py` (`main`). Add tests for each, and make `launch` report clearly when the agent program exits straight back to a shell prompt instead of saying only that the prompt is not ready.
