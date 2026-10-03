# Routing: which provider and model gets a job

The orchestrator is meant to use more than one subscription well. To do that it has to know which agent tools and models a machine can use, how much usage each has left, and then pick a provider and model for each job and say why. This document is the specification for that logic.

## The model

Five small ideas. Everything else follows from them.

- **Provider**: an agent tool that runs in a terminal (Codex, Claude Code, later OpenCode, Aider, Cursor, a local model). One adapter each.
- **Class**: what a model is good for, in three levels: `fast`, `workhorse`, `frontier`. Jobs ask for a class, never for a model name.
- **Budget**: how much of a provider's usage window is left, and whether it is being spent faster than the window allows.
- **Job**: one task file, a tier (`easy`, `standard`, `hard`), and a role (`make` or `check`).
- **Decision**: provider, model, effort, and the reasons, printed and logged.

## Logic

### 1. Inventory: what can this machine use

Each adapter answers the same questions and says "unknown" instead of guessing:

| Question | Codex | Claude Code | Others |
|---|---|---|---|
| Installed? | `codex` on PATH or the known install folder | `claude` on PATH | binary on PATH |
| Signed in? | `codex login status` | `claude` auth check | per tool, else unknown |
| Models | `models_cache.json` | list in config, default `fable`, `opus`, `sonnet`, `haiku` | config |
| Efforts | per model, from the same file | `--effort` levels | none |
| Usage | newest `rollout-*.jsonl` `rate_limits` | `cswap list --json` if present, else unknown | local models: no limit |

`cco inventory` prints this as a table. Account names, emails and organisation names are never printed or logged.

### 2. Classes: which model is which

Each model gets a class from, in order: an override in `cco.toml`; the provider's own description ("frontier", "workhorse", "fast"); a built in table for known names. A model with no class is listed and not used until the person classes it.

Tier to class: `easy` needs `fast`, `standard` needs `workhorse`, `hard` needs `frontier`. A higher class always satisfies a lower tier.

### 3. Budget: how much is left

For each window a provider reports: percent used, time to reset, and pace (percent used against percent of the window elapsed). The worst window governs. That gives one state per provider:

- `ok`: under pace.
- `tight`: ahead of pace, or less than 30% left.
- `critical`: less than 10% left, or projected to run out before the reset.
- `exhausted`: the provider says the limit is reached.
- `unknown`: no reading, or the reading is older than a set age. Codex figures are only as fresh as the last Codex turn, so the age is always shown.

Unknown is never treated as plenty.

### 4. Routing: which provider and model gets the job

1. Candidates: every model on an installed, signed in provider whose class meets the tier.
2. Drop providers that are `exhausted`.
3. Prefer the lowest class that meets the tier. A `fast` model does `easy` work even when `frontier` is free.
4. Among equals, prefer the provider in the better budget state; if tied, the one furthest under pace, so both subscriptions are spent evenly.
5. Protect the orchestrator. The Claude Code session doing the directing spends Claude usage too, so Claude workers are not used once Claude is `tight`, and a floor is kept back for directing and checking (default: the last 25% of the 5 hour window).
6. A job can pin a provider or model. The pin wins and the decision says it was pinned.
7. If nothing is `ok` or `tight`:
   - `easy` and `standard` jobs step down one class, with the reason stated;
   - `hard` jobs stop and ask the person;
   - if everything is exhausted, the job is held and the earliest reset time is shown.

`cco route --tier hard --explain` prints the decision without launching anything, for example: "codex gpt-6-astra medium. Tier hard needs frontier. Codex 7 day window 18% used, under pace. Claude 7 day window 62% used, projected to run out before reset, so not used for workers."

### 5. Make, then check

For bulk work the cheap model makes and a stronger model checks whether the result is right.

- `cco launch --tier easy --check` runs the maker, waits for it, then launches a checker on the same folder.
- The checker is one class above the maker, at least `workhorse`, and comes from the **other** provider when there is one, so the second opinion is independent. Codex makes and Claude checks, or the reverse.
- The checker is read only: it writes a findings file and changes nothing. If it finds problems, the maker gets one follow up with the findings. A second failure goes to the person.
- The orchestrator still looks at the result itself. A checker's report is evidence, not proof.

### 6. The run log

One line per agent: job kind, tier, role, provider, model, effort, the budget states at launch, duration, how it ended, and later whether the person accepted the result or it was redone. `cco log` summarises it: which tier and model combinations needed redoing, and the change in each provider's percent while an agent ran. That change is a rough cost figure and only means something when one agent ran at a time; the summary says so.
