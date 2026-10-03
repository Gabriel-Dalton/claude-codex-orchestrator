# Lessons behind Claude Codex Orchestrator

## 1. Restored terminals produce duplicate agents

What happened: launching after an Orca restart gave two agents the same job.
Why: Orca restores terminals, and the restored processes may still be useful.
CCO lists live terminals before creating one and checks target folder metadata,
recognized folder footers, and owned records. A deliberate duplicate requires
`--force`. A partial terminal list blocks launch.

## 2. Sending a task is not completion

What happened: a coordinator assumed an agent was done without observing it.
Why: terminal creation and input acceptance do not mean a Codex turn ended.
CCO waits for an explicit report path, open PR for a branch, or idle screen.
It distinguishes done, timeout, Orca gone, and terminal gone with exit codes.
The reviewer still reruns checks and examines the result.

## 3. Orca can disappear

What happened: commands failed after the app exited.
Why: the command line needs a running runtime. Starting the app as a child of a
short-lived process can also tie its lifetime to that process.
CCO reports the missing runtime plainly. `doctor --start` calls `orca open`,
the app's own launcher, rather than starting the application executable as a
managed child. Current help says it waits for runtime readiness, so an immediate
return is not guaranteed. Shutdown behavior was not tested on a shared runtime.

## 4. A git worktree is not necessarily registered in Orca

What happened: terminal creation for an unknown folder timed out waiting for a
handle. Why: filesystem existence and Orca workspace registration differ.
CCO checks discovery after the specific timeout, then falls back to a registered
ancestor or the main repository found through git's common directory. The
command retains `codex -C <target>` so the agent works in the assigned worktree.
If any new terminal appeared, CCO stops rather than risking duplicate creation.

## 5. A submitted-looking prompt can still be a draft

What happened: send reported no observed turn start, and the agent did nothing.
Why: text acceptance and actual submission are separate events. A new folder
can also show a trust prompt before the agent is ready.
CCO reads the rendered screen, accepts a recognized folder-trust prompt first,
sends the short task pointer, and checks for working or a newly completed turn.
If that exact text remains in `draft`, it presses Enter once more without typing
the text again. Unconfirmed agents remain recorded for inspection.

## 6. Model choice needs to be explicit

What happened: the selected model did not fit the scope or risk of a job.
Why: delegating without a visible model choice hides an important decision.
CCO maps three tiers to a model and effort in `cco.toml`, supports explicit
overrides, records the result, and prints the selection at launch. Model quality
and availability still need independent assessment.

## 7. Long terminal prompts are fragile briefs

What happened: detailed instructions became difficult to submit and review.
Why: a terminal input is a poor home for a long, changing task specification.
CCO requires an existing task file within the assigned folder and sends one
line pointing to it. Templates ask for rules, one job, limits, checks, and a
report. The task file stays reviewable alongside the work.

## Windows needs a real terminal

Running Codex without a real terminal on Windows can leave it read-only. CCO
uses Orca terminal sessions instead of launching Codex through captured pipes.
The automated suite never launches a real agent. The permitted live check used
one plain shell command and closed only the terminal it created; Orca returned
an unavailable screen, so the shell output could not be verified.
