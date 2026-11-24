---
name: squad-delegate
description: This skill should be used when work needs to be split across multiple specialized agents (architect, reviewer, security-auditor, etc.) with context and decisions persisted between them — trigger phrases include "delegate this to the squad", "hand this off", "run this by the architect/reviewer", or any multi-step task where different personas should own different phases. Reads and writes the .squad/ persistence layer so state survives across agent invocations and sessions.
version: 0.1.0
---

# Squad Delegate (Multi-Agent Context Handoff)

Orchestrates handing work between the persistent agent personas defined
in `.claude/agents/` (architect, reviewer, security-auditor, ...) using
the file-backed state under `.squad/` as the shared memory layer. Agents
don't share a chat history — this skill is what lets one agent's output
become the next agent's input without losing context, following the
supervisor/worker coordination pattern: a delegator routes work and
records the routing decision, rather than agents freely paging each
other.

## The `.squad/` layout this skill reads and writes

- `.squad/tasks/` — one markdown file per task, status tagged `[TODO]`,
  `[IN_PROGRESS]`, `[DONE]`, `[BLOCKED]`. This is the work queue.
- `.squad/context/<role>.md` — the current state snapshot for each
  persona (architect, reviewer, security-auditor). What that role needs
  to know to pick up work without re-deriving it.
- `.squad/mailbox/` — one file per message, named
  `<timestamp>-<from>-to-<to>.md`, for handoff notes between roles. Read
  and delete (or archive) on pickup; don't leave stale mail unread.
- `.squad/DECISIONS.md` — append-only log of architectural decisions
  made during delegation, newest at the bottom. Every decision that
  changes a previous plan gets an entry here, not just a chat message.

## Delegation procedure

1. **Before delegating**, write or update the task file in
   `.squad/tasks/` describing the unit of work and its status.
2. **Write a handoff note** to `.squad/mailbox/` addressed to the
   receiving role: what's done, what's expected next, any constraints
   discovered so far. Assume the receiving agent has *no* memory of this
   conversation — the note must be self-contained.
3. **Invoke the receiving persona** (via the Agent tool, using the
   agent definition in `.claude/agents/<role>.md`) with the mailbox note
   as its brief.
4. **On completion**, update `.squad/context/<role>.md` with the new
   state, mark the task file's status, and if the work involved a
   decision with lasting consequences, append it to
   `.squad/DECISIONS.md` with a one-line rationale.
5. **Never silently drop a role's output.** If a persona's result
   contradicts an existing decision in `DECISIONS.md`, surface the
   conflict to the user rather than picking a side automatically.

## Rules

- Context snapshots in `.squad/context/` are overwritten, not appended —
  they represent *current* state, not history. History lives in
  `DECISIONS.md` and the mailbox archive.
- Keep task files small and single-purpose; don't let one task file
  become a running log for the whole project.
- `bin/squad` provides the CLI form of these operations
  (`squad task add/list/done`, `squad mail send/read`, `squad decide`) —
  prefer it over hand-editing files where a subcommand already exists,
  so status stays consistent.
