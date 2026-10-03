# Task 01 report: Claude Codex Orchestrator

## Built

Implemented the `cco` Python package, `python -m cco`, and the `cco` console
entry. Commands include doctor, launch, list, wait, peek, send, stop, and task
new. Orca command handling and Codex screen interpretation are separate modules.
Launch checks for duplicates, supports registered-repository fallback, sends a
single task-file pointer, and keeps ownership state even if submission fails.
Terminal incarnation checks protect against acting on a replaced process.

Added `cco.toml`, per-user atomic state with a mutation lock, four task templates,
the Claude Code skill, README, CLI observations, lessons, and the MIT license.
The package has a standard-library build backend and no dependencies. Applied
the requested rename throughout source, tests, docs, instructions, configuration,
state naming, and the self-test title. The local directory was not renamed.

## Verification

- `python -m unittest`: 26 tests passed. A subprocess fake covers duplicate
  refusal, unknown-folder fallback, ambiguous creation, draft retry, folder
  trust, all four wait outcomes, reports, multiple agents, PR checks, model
  selection, ownership, incarnation changes, configuration, and CLI routing.
- Wheel and source archive builds passed without installing packages. An
  unpacked wheel ran the task-template command successfully.
- `python -m cco doctor`: passed on this machine, found both executables,
  reported Orca running, printed the tier table, and grouped terminal handles.
  Live output was not written into the repository.
- Exactly one live terminal was created, titled `cco-selftest`, through the
  normal launch path with the agent command replaced by a plain shell echo.
  No Codex agent was launched. The terminal was read and closed in a finally
  block, and its owned record is marked stopped.
- The live output assertion did **not** pass: the read returned an empty
  `screen-unavailable` response. The first read also exposed a nested payload
  assumption, which was fixed and covered by the fake. A subsequent raw read of
  the same terminal confirmed the unavailable screen. No second terminal was
  created because the task allowed exactly one. Full live acceptance remains
  incomplete.
- `git diff --check` passed. A scan of repository source, including hidden
  project files, found no old product name, real local user paths, account or
  project identifiers observed during discovery, email addresses, token
  patterns, or em dashes. Generated Python caches were removed. Git's internal
  metadata was excluded from the publishable-file scan and left untouched.

## CLI differences and observations

`terminal read --screen --json` nests its fields under `result.terminal`, and
`tail` is an array of lines. Help explicitly distinguishes rendered screens,
streams, unavailable screens, and unsent draft text. CCO handles that envelope
and treats unavailable screens as needing inspection.

Current `orca open` help says it waits for runtime readiness, rather than
promising an immediate return. Send help distinguishes accepted input from
observed submission and turn start, and exposes wait/retry receipt flags. CCO
does not depend on the unverified receipt schema; it verifies screen state and
retries only Enter when the exact prompt remains in the draft. List responses
include incarnation IDs, host scope, and truncation status, which CCO checks.

## Not tested live

Real Codex task execution, trust acceptance, draft resubmission, unknown-folder
creation timeout, Orca shutdown/restart and detached startup, and authenticated
PR discovery were not exercised. Existing terminals belonged to other work and
were only listed. Screens and mutations targeted only the created self-test
terminal. The fake tests exercise the corresponding failure paths but cannot
establish live behavior.

## Next

In a separately authorized live test, allow the shell to become ready and
investigate Orca's unavailable screen before asserting its output. Then verify
a full Codex turn, a fresh report, a folder-trust prompt, and runtime restart
recovery in an isolated environment. Add fixtures for any new screen layouts or
receipt schemas observed there. No cost or speed claims have been measured.

No commit, push, package installation, or other terminal mutation was performed.
