# Role Context Snapshots

One file per persona: `architect.md`, `reviewer.md`,
`security-auditor.md`. Each file is the *current state* for that role —
overwritten on update, not appended to. History belongs in
`../DECISIONS.md` (decisions) or `../mailbox/` (handoff notes), not
here.

A role reads its own snapshot at the start of a session to avoid
re-deriving context, and writes an updated snapshot before handing off
or finishing. Keep each snapshot short — a running "what I know right
now" summary, not a transcript.

Files are created on first use by the corresponding persona; none are
seeded here so the first real snapshot isn't stale example text.
