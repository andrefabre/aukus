---
description: Dispatch a self-contained goal to GitHub Copilot CLI's /fleet parallel-agent mode in the background and log the session under .squad/logs/
argument-hint: <self-contained goal description>
allowed-tools: Bash(bin/fleet:*)
---

Run `bin/fleet "$ARGUMENTS"` to dispatch this goal to Copilot CLI's
`/fleet` orchestrator as a non-interactive background job.

Before running it, check that `$ARGUMENTS` is genuinely self-contained:
Copilot's fleet subagents do not inherit this conversation's history, so
a vague or context-dependent goal ("do the thing we discussed") will
fail or run sequentially instead of in parallel. If the argument is
missing context the receiving agent would need (target files, acceptance
criteria, constraints), expand it before calling `bin/fleet` rather than
passing it through as-is.

After dispatch, tell the user the log path
(`.squad/logs/fleet-<timestamp>.log`) and that `bin/fleet status` shows
progress — do not poll it yourself in a loop.
