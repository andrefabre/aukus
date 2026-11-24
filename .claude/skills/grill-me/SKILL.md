---
name: grill-me
description: This skill should be used when the user asks to stress-test a design, architecture, or plan before code gets written — trigger phrases include "grill me", "poke holes in this", "play devil's advocate", "stress-test this design", or "before we build this, challenge it". Runs a Socratic questioning pass over a proposal to surface unstated assumptions and failure modes before implementation starts.
version: 0.1.0
---

# Grill Me (Socratic Design Stress-Test)

A user-invoked pass that challenges a design decision *before* code gets
written, rather than reviewing it after. The goal is to surface weak
assumptions while they're still cheap to change.

## When to use

Only when explicitly invoked, or when the user is about to commit to a
non-trivial architectural choice (new service boundary, data model,
public API shape, concurrency model) and hasn't already had it
challenged. Don't run this on trivial or already-reversible decisions —
save it for choices that are expensive to undo.

## The pass

Ask questions in these categories, in order, stopping early if the
proposal already has clearly correct answers:

1. **Necessity** — What problem does this actually solve? What happens
   if we do nothing? Is there a simpler version that solves 80% of it?
2. **Assumptions** — What is this design assuming about scale, traffic
   shape, data size, or user behavior? What breaks if that assumption is
   wrong by 10x?
3. **Failure modes** — What's the failure mode when a dependency is
   slow, down, or returns garbage? Is that failure mode acceptable, or
   does it cascade?
4. **Reversibility** — If this turns out to be wrong in three months,
   what does undoing it cost? Is there a cheaper reversible version to
   ship first?
5. **Alternatives** — What's the most boring, conventional way to solve
   this? Why isn't that the answer?
6. **Ownership** — Who has to operate, debug, and extend this after
   today? Does the design match their skill level and tooling?

## Rules

- Ask, don't answer. The point is to make the user (or the proposing
  agent) defend the design out loud — don't immediately supply the
  counterargument's resolution unless asked.
- Push back at least once on the first answer given to each question if
  it's vague ("it should scale fine") — ask for the specific number or
  mechanism.
- End with a short list of the assumptions that survived unchallenged
  vs. the ones that changed the design. Don't end with a verdict of
  "approved" or "rejected" — that's the user's call, not this skill's.
