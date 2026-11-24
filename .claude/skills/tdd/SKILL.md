---
name: tdd
description: This skill should be used when the user asks to implement a feature, fix a bug, or write new logic and wants it built test-first — trigger phrases include "TDD this", "red-green-refactor", "write the test first", "implement with tests", or any request to add behavior to code that already has a test suite. Enforces that a failing test exists before implementation code is written.
version: 0.1.0
---

# TDD (Red-Green-Refactor Enforcement)

Enforces the strict red-green-refactor loop. This skill exists to stop
implementation code from being written before a failing test proves the
behavior is missing — the most common shortcut agents take under time
pressure, and the one that produces the least trustworthy code.

## The loop

1. **Red** — write (or extend) a test that expresses the desired behavior.
   Run it. Confirm it fails, and confirm it fails **for the expected
   reason** (missing behavior, not a typo or import error). Paste the
   failing output before moving on.
2. **Green** — write the minimum implementation code needed to make that
   test pass. Do not add behavior the test doesn't demand. Run the test.
   Confirm it passes. Run the full suite to confirm no regression.
3. **Refactor** — with the safety net of a passing suite, clean up
   duplication or naming in the code just written. Re-run the suite after
   every refactor step. Do not change behavior during this step.

Repeat per unit of behavior. Small increments — one assertion or one
branch at a time — not one giant test for the whole feature.

## Hard rules

- Never write implementation code before a failing test exists for it.
- Never mark a step done without having actually run the test command and
  observed the result — do not infer pass/fail from reading the code.
- If a test can't be made to fail first (e.g. pure config, generated
  code), say so explicitly and name the exception instead of silently
  skipping the loop.
- If the user's request has no test infrastructure in place yet, set up
  the minimal runner/harness first, prove it runs a trivial failing test,
  then proceed with the loop.

## Reporting

At each Red step and each Green step, show the actual command run and
its output — not a paraphrase. This is what makes the loop verifiable
instead of asserted.

See [references/failure-modes.md](references/failure-modes.md) for
common ways this loop gets silently skipped.
