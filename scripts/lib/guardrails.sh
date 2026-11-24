#!/usr/bin/env bash
# guardrails.sh — shared logic for git-guardrail enforcement.
# Sourced by .githooks/pre-commit, .githooks/pre-push, and bin/check-guardrails
# so the rules are defined once instead of duplicated between hooks and the
# human-facing CLI. See .claude/skills/git-guardrails/SKILL.md for the policy
# this implements.

PROTECTED_BRANCHES="${AGENTIC_PROTECTED_BRANCHES:-main master}"

guardrail_current_branch() {
  git symbolic-ref --quiet --short HEAD 2>/dev/null || echo "HEAD"
}

guardrail_is_protected_branch() {
  local branch="$1"
  local b
  for b in $PROTECTED_BRANCHES; do
    [[ "$branch" == "$b" ]] && return 0
  done
  return 1
}

# guardrail_is_force_push <old-sha> <new-sha>
# A push is a force/non-fast-forward push if old-sha is not an ancestor of
# new-sha (and old-sha isn't the all-zero "new branch" sentinel).
guardrail_is_force_push() {
  local old="$1" new="$2"
  [[ "$old" =~ ^0+$ ]] && return 1   # new branch/ref, not a force push
  git merge-base --is-ancestor "$old" "$new" 2>/dev/null && return 1
  return 0
}

# guardrail_staged_skill_files — SKILL.md files currently staged for commit
guardrail_staged_skill_files() {
  git diff --cached --name-only --diff-filter=ACM -- '.claude/skills/*/SKILL.md' 2>/dev/null
}

# guardrail_staged_shell_files — *.sh / bin/* shell scripts staged for commit
guardrail_staged_shell_files() {
  git diff --cached --name-only --diff-filter=ACM 2>/dev/null \
    | grep -E '(\.sh$|^bin/[^/]+$|^\.githooks/[^/]+$)' || true
}
