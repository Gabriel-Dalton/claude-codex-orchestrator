---
name: claude-codex-orchestrator
description: Direct Codex agents in Orca terminals with the cco command line.
---

# Claude Codex Orchestrator

Use this playbook in Claude Code when a job can be briefed and checked
independently. Do small edits directly when briefing and reviewing would be
more work than the edit. Claude Code defines the task and reviews the result;
Codex does the assigned implementation.

1. Read the target repository's rules. Run `python -m cco doctor` or
   `python -m cco list --all` before launching and after every Orca restart.
   Restored terminals may already be doing the job.
2. Assign one agent per folder. For parallel work on one repository, give each
   agent its own git worktree and branch. When other sessions share the
   repository, tell the person which folders and branches are taken.
3. Create a task with `python -m cco task new --kind feature --out TASK.md`.
   Fill it in before launching: one job, repository rules, acceptance checks,
   limits, forbidden files and actions, and a report path. Keep instructions in
   the file. The launch prompt is only a pointer to it.
4. Choose easy for one-file fixes and copy, standard for ordinary code changes
   with tests, and hard for design or costly mistakes. Run
   `python -m cco launch --dir ~/code/example-app --task TASK.md --tier standard`.
   Tell the person the printed model and effort for each agent. Use the printed
   agent id for all later commands. Do not use `--force` to bypass uncertainty.
5. Start `python -m cco wait <id> --done report:TASK.report.md --timeout 30`
   as a background task using Claude Code's background execution facility so
   the session receives completion. Use a fresh report path for each job.
   `--done pr:feature/example` needs an authenticated `gh`; `--done idle` only
   signals a finished turn, not a correct result. Exit codes: 0 signal observed,
   2 timeout, 3 Orca gone, 4 terminal gone. Inspect errors, never assume done.
6. Use `peek <id>` to inspect and `send <id> "..."` for a follow-up. If submission
   is unconfirmed, inspect first. Never send the same job blindly a second time.
7. Treat the report as a claim. Review the diff and resulting behavior, rerun
   the relevant checks, and report your own verification to the person.
8. Stop agents no longer needed with `stop <id>` or `stop --all-mine`.
   Never close another session's terminals. Do not merge, commit, push, or
   deploy unless the person and repository rules authorize it.

Run from the tool checkout or use the installed `cco` command. Task paths are
relative to `--dir`; report paths are relative to each agent's target folder.
