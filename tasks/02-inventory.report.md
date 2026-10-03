# Task 02 report: providers, inventory and usage

Built the provider interface, Codex, Claude and generic adapters, inventory,
class mapping, and budget evaluation. `inventory` and `usage` support text and
JSON output without Orca. Class overrides precede descriptions and the built-in
table. Unclassified models remain visible and unusable. Budget thresholds and
freshness limits are configurable. The worst usage window governs.

Moved Codex screen interpretation into its provider, retaining compatibility
exports. Existing tier selection and terminal launch mechanics remain intact.
Package builds now include the provider subpackage and invented test fixtures.

Fixed clean-start placeholder drafts, added a clear shell-exit diagnostic, and
covered Windows folder quotes and Unicode console output. `send` queues a
follow-up during work. When Orca reports no new turn start and the exact message
remains in the draft, it retries Enter once without retyping the message.

Configuration now defaults to the user config folder. A working-folder file is
ignored with one stderr notice unless explicitly selected by `--config` or
`CCO_CONFIG`. Only those trusted sources supply `agent_command`. Model, effort
and provider names use the required strict identifier validation. Folder paths,
task paths and titles use the requested character allow list before shell
quoting, including validation after path resolution. README and lessons explain
the trust rule and shell expansion risk.

## Observed source shapes

Inspected real local files and read-only status commands without copying them
or saving account data. Codex model efforts are objects with an `effort` field
and a description. Usage records place `rate_limits` inside an event payload;
the timestamp is on the enclosing record. The secondary window can be null.
Extra credit, individual-limit and spend-control fields are not interpreted.
The provider uses the latest valid rate-limit record in the newest rollout,
not the file modification time as the reading timestamp.

The account switcher returns an object containing `accounts`, with both an
active flag and an active account number. Window resets are ISO timestamps.
Account-level `usageFetchedAt` and `usageAgeSeconds` supply freshness. Pace and
projection fields can be absent from the five-hour window. Extra account,
organization, scoped-window and recommendation fields are excluded. Claude auth
returns `loggedIn`; other fields are discarded. Only invented fixtures were
written to this repository.

## Verification

- `python -m unittest`: 51 tests passed, including all budget states, freshness,
  both Claude windows, class precedence, provider absence, privacy, queued
  messages, hostile config, rejected shell characters, packaging and prior
  orchestration checks. Tests require no installed agent tools.
- Both text and JSON forms of live inventory and usage completed successfully.
  Codex was installed, models were present, and a timestamped usage reading was
  present. Real percentages, account details and paths were not saved.
- Privacy search checked publishable tracked and untracked files for local
  identity and paths, non-example email addresses, token patterns and em dashes.
  No findings. Ignored caches and Git metadata were excluded.
- `git diff --check` passed. No commit, push, package install, live agent launch
  or terminal mutation was performed.

## Unknowns and limits

Claude efforts remain unknown unless configured. `fable` has no assumed class;
it needs an override. Generic sign-in status, models and usage remain unknown
unless supported or configured; installed local Ollama usage is unlimited.
Missing or stale telemetry stays unknown. No Codex exhaustion projection is
invented when the source provides none. Claude and generic launching and screen
reading are not implemented. Live terminal behavior for these fixes was not
exercised; the subprocess fake supplies the regression evidence.

The pre-existing change to `tasks/01-build.report.md` was left untouched.
