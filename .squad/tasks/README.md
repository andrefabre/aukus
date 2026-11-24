# Task Queue

One markdown file per task, named `NNN-short-slug.md` (zero-padded,
sequential). Status lives in the frontmatter and in the visible tag at
the top of the body so it's readable both by tooling and by a human
scanning the directory.

Use `bin/squad task add "<title>"` to create one instead of hand-rolling
the format — it assigns the next number and fills the template.

## Status tags

- `[TODO]` — not started
- `[IN_PROGRESS]` — a role/agent is actively working it
- `[BLOCKED]` — stalled, reason must be stated in the body
- `[DONE]` — complete, verified

## Template

```markdown
---
status: TODO
owner: unassigned
created: YYYY-MM-DD
---

# [TODO] <title>

## Goal
What "done" looks like.

## Context
Why this task exists, links to relevant mailbox notes or decisions.

## Notes
Running log of progress, appended to as work happens.
```

See [000-example.md](000-example.md) for a filled-in instance.
