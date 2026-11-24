---
description: Print the current squad state — open tasks, unread mailbox notes, and the tail of DECISIONS.md — so an agent or human can pick up context fast
argument-hint: (no arguments)
allowed-tools: Bash(bin/squad:*)
---

Run `bin/squad status` and present its output.

This surfaces, in order: open tasks in `.squad/tasks/` grouped by
status, any unread notes in `.squad/mailbox/`, and the most recent
entries in `.squad/DECISIONS.md`. Use this at the start of a session
that continues prior squad work, or whenever picking up a task another
agent/persona left in `[IN_PROGRESS]` or `[BLOCKED]` state, so decisions
already made aren't re-litigated from scratch.
