# Mailbox

Inter-agent handoff notes. One file per message:

```
<YYYYMMDDHHMMSS>-<from>-to-<to>.md
```

e.g. `20260807143000-architect-to-reviewer.md`.

Written by `bin/squad mail send <from> <to> "<message>"` or by an
agent/skill directly (see the `squad-delegate` skill). A note must be
self-contained — the receiving agent has no memory of the sending
agent's conversation, so restate goal, constraints, and current state
rather than referring back to "what we discussed."

On pickup, the receiving role should either delete the file or move it
to `.squad/mailbox/archive/` (create that directory on first use) —
don't leave read mail sitting in the inbox, it makes `bin/squad status`
noisy for the next role.
