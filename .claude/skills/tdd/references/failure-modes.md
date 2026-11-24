# Common ways red-green-refactor gets silently skipped

- **Writing test and implementation in the same edit.** Even if both are
  in the same commit, the test must be *run* in a failing state before
  the implementation is written. Simultaneous authorship isn't the loop.
- **A test that "fails" because of a typo or missing import.** That's not
  red for the right reason. Fix the scaffolding, re-run, confirm the
  failure is the actual missing-behavior assertion.
- **Skipping refactor because green feels done.** Green is not the exit
  condition — refactor with the safety net while it's cheap, not later
  when the surrounding code has grown.
- **Batching many behaviors into one test before running anything.**
  Defeats the fast-feedback purpose of the loop. One behavior, one
  red/green cycle.
- **Trusting a mental simulation of the test result instead of running
  it.** If the test command wasn't actually executed this turn, the
  step isn't done.
