# Orca command line observations

Observed on 2026-10-03 using installed CLI help, repository/worktree listing,
terminal listing, and one permitted shell terminal. Examples below use invented
values. No live terminal output, account details, or local user paths are stored
here. Existing terminals were only listed, never individually read or changed.

## Discovery performed

Read `orca --help`, group help for `repo`, `worktree`, and `terminal`, and help
for every subcommand listed in those groups:

- repo: list, add, show, set-base-ref, search-refs.
- worktree: list, show, current, create, set, rm, ps.
- terminal: list, show, read, send, wait, create, rename, split, switch, focus,
  close. Focus aliases switch.

Also read `open` and `status` help. CCO uses only the commands below; it does not
create worktrees, register repositories, focus terminals, or close whole tabs
or workspaces. All terminal reads and mutations name a specific handle.

## JSON envelope

Observed responses use this shape, with command-specific `result`:

```json
{"id":"request_example","ok":true,"result":{},"_meta":{"runtimeId":"runtime_example"}}
```

Failures may be text on stderr or a JSON error with `ok: false`. CCO checks both
exit status and `ok`. Unavailable-runtime text is documented as
`Orca is not running. Run 'orca open' first.` This was tested with the fake CLI;
the shared live application was not stopped to reproduce it.

## Commands used by CCO

### `orca terminal list --limit 100000 --json`

Help also supports `--worktree <selector>` and `--include-visual-layouts`.
CCO requests a large cap and rejects `truncated: true` or omitted hosts. List
previews are metadata returned by discovery, not individual screen reads.

```json
{"terminals":[{"handle":"term_example","ptyId":"repo_example::/projects/example-app@@pane_example","incarnationId":"process_example","orphaned":false,"worktreeId":"repo_example::/projects/example-app","worktreePath":"/projects/example-app","branch":"refs/heads/feature/example","tabId":"tab_example","leafId":"leaf_example","title":"example-task","connected":true,"writable":true,"lastOutputAt":null,"preview":"invented preview","executionHostId":"local","agentIdentity":"codex"}],"hostScope":{"hostIds":["local"],"omittedHostIds":[]},"topologyRevisions":{},"totalCount":1,"truncated":false}
```

Orphaned entries can have empty folder paths. Handles and incarnation IDs are
distinct. CCO refuses to act on a saved handle if its incarnation changed.

### `orca repo list --json`

Used to find a registered ancestor or a sibling worktree's main repository.
The result has `repos`, whose entries include `id`, `path`, `displayName`, and
additional metadata CCO does not retain.

```json
{"repos":[{"id":"repo_example","path":"/projects/example-app","displayName":"example-app","kind":"git"}]}
```

`orca worktree list --json` was also inspected during discovery. Its `worktrees`
entries have `id`, `path`, `repoId`, `branch`, and identity/host metadata, with
`hostScope`, `totalCount`, and `truncated` alongside. CCO does not need this
command at runtime.

### `orca terminal create --worktree path:<folder> --title <title> --command <command> --json`

Help confirms `--shell <shell>` and `--focus` as optional flags. CCO does not
request focus. `--command` is typed into the host shell, so shell quoting matters.
On Windows `--shell` can select the terminal's shell; it is different from
starting a nested shell through `--command`.

The live creation returned a handle under `result.terminal`:

```json
{"terminal":{"handle":"term_example","incarnationId":"process_example"}}
```

Additional fields may be present. An unknown folder's reported failure,
`Timed out waiting for terminal handle after creation`, was covered with the
fake CLI. It was not deliberately reproduced live because only one terminal
creation was permitted. CCO checks for a newly appeared terminal before trying
the registered-repository fallback.

### `orca terminal read --terminal <handle> --screen --json`

Help also supports `--limit <n>` and `--cursor <n>`; `--screen` and `--cursor`
are mutually exclusive. CCO uses the rendered screen because the default stream
can contain repeated fragments from TUI repainting.

The live payload nests the read under `terminal`, rather than returning `tail`
at the top of `result`. `tail` is a list of lines:

```json
{"terminal":{"handle":"term_example","status":"running","tail":[],"truncated":false,"limited":false,"oldestCursor":"0","nextCursor":"0","latestCursor":"0","returnedLineCount":0,"source":"screen-unavailable"}}
```

The live self-test returned this empty, unavailable screen. Help documents
`source: screen`, `stream`, and `screen-unavailable`. When present, `draft` is
UI composer text separate from terminal output. Its behavior with a real Codex
agent was not exercised. The fake uses a string draft and rendered screen lines.

### `orca terminal send --terminal <handle> --text <text> --enter --json`

For the one allowed retry CCO omits `--text` and sends only `--enter`.
Help also exposes `--interrupt`, `--wait-submit <seconds>`, and
`--retry-request <id>`. Input acceptance, submission observation, and turn start
are separate. `--wait-submit` observes without resending. Retry IDs bind to the
exact payload and process incarnation. Older hosts may offer only raw input.

No live send was made. The exact receipt schema remains unverified, so CCO
does not depend on it. The fake receipt is intentionally minimal:

```json
{"inputAccepted":true}
```

CCO confirms submission by reading the screen and never blindly retypes a
prompt after an ambiguous transport failure. It handles the known no-turn-start
message by inspecting the draft and screen before deciding what happened.

### `orca terminal close --terminal <handle> --json`

Closes one pane/session. CCO never uses `--tab` or `--worktree ... --all`, which
can close broader sets of terminals. The permitted self-test terminal was
successfully closed. CCO uses success status and does not depend on close
result fields. The fake result is `{"closed":true}`; that is a fixture, not a
claim about the live response schema.

### `orca open --json`

Used only by `doctor --start` when discovery reports Orca unavailable. Current
help says it launches Orca and waits for the runtime to be reachable, which
differs from a guarantee that it returns immediately. CCO uses the launcher and
does not keep the GUI as a managed child. No live start or shutdown was attempted;
the JSON body is unused and its schema is unverified.

## Codex observations and limits

The supplied known screen markers are `Working (1m 02s`, `Worked for 5m 21s`,
and `Ask Codex to do anything`, with model, effort, and folder in the footer.
List previews were consistent with those markers but are flattened and can
contain repaint fragments. CCO's parser is isolated in `cco/codex.py` and tested
with invented examples. Real trust prompts, real draft retries, and a complete
Codex turn were not tested because the live restriction prohibited agents.
