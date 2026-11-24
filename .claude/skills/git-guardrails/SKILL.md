---
name: git-guardrails
description: This skill should be used whenever a git command is about to run that rewrites history, force-pushes, resets, cleans working state, or pushes directly to a protected branch — trigger phrases include "push this", "force push", "reset hard", "clean the repo", or any git operation with a destructive or hard-to-reverse blast radius. Requires explicit human approval before those commands run, and defers to the repo's .githooks enforcement as the actual backstop.
version: 0.1.0
---

# Git Guardrails

Blocks destructive git actions from running without explicit human
approval. This skill is the agent-side half of the guardrail; the
repo-side half is the enforced hook in
[.githooks/pre-push](../../../.githooks/pre-push) and
[.githooks/pre-commit](../../../.githooks/pre-commit), installed via
`scripts/install-aliases.sh`. Treat the hooks as the real backstop —
this skill exists so the agent never even attempts the blocked command
and has to ask first, instead of finding out from a hook failure.

## Commands that always require explicit human confirmation first

- `git push --force` / `--force-with-lease`
- `git reset --hard`
- `git clean -f` / `-fd`
- `git checkout -- <path>` or `git restore <path>` (discards uncommitted
  work)
- `git push` directly to `main`/`master` (vs. opening a PR from a branch)
- `git branch -D` (force delete, as opposed to `-d`)
- Rewriting published history: `git rebase` on a branch already pushed
  and shared, `git commit --amend` on a published commit, `git
  push --force` after either

## Procedure

1. Before running any command in the list above, stop and state plainly
   what the command will do and what it puts at risk (lost commits,
   overwritten remote history, discarded uncommitted work).
2. Ask the user to confirm explicitly — do not treat a prior unrelated
   approval, or an "auto mode" setting, as covering this. Scope of
   approval is the specific command, not "git operations" in general.
3. If the command is refused, look for a non-destructive alternative
   (e.g. `git revert` instead of `reset --hard`, a new branch instead of
   force-pushing over a shared one) and propose it.
4. If the local `.githooks` are installed, expect the hook to reject the
   command a second time regardless of this skill's check — that's
   correct defense-in-depth, not a bug. `AGENTIC_ALLOW_FORCE_PUSH=1` /
   `AGENTIC_ALLOW_MAIN_PUSH=1` env vars are the human's explicit override
   for the hook layer; never set those on the user's behalf.

## Explicitly not covered

Regular `git add`, `git commit` (on a feature branch), `git push` (to a
non-default branch), `git pull`, `git fetch`, `git merge` (fast-forward
or with a normal merge commit) — these are reversible or low-risk and
don't need this ceremony.
