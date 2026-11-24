#!/usr/bin/env bash
# install-aliases.sh — one-time setup for this repo:
#   1. Points git at .githooks/ so the guardrail hooks are actually enforced
#      (core.hooksPath isn't set by `git init`/`git clone` — must be opted in).
#   2. Ensures bin/ scripts are executable.
#   3. Prints shell aliases (fleet, squad) to add to your shell rc file.
#
# Usage: bash scripts/install-aliases.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "Setting core.hooksPath to .githooks ..."
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit .githooks/pre-push

echo "Ensuring bin/ and scripts/ are executable ..."
chmod +x bin/fleet bin/squad bin/check-guardrails
chmod +x scripts/install-aliases.sh scripts/validate-skills.sh

RC_SNIPPET=$(cat <<EOF
# --- agentic-workflow aliases ---
export AGENTIC_WORKFLOW_ROOT="$ROOT"
alias fleet="\$AGENTIC_WORKFLOW_ROOT/bin/fleet"
alias squad="\$AGENTIC_WORKFLOW_ROOT/bin/squad"
alias check-guardrails="\$AGENTIC_WORKFLOW_ROOT/bin/check-guardrails"
# --- end agentic-workflow aliases ---
EOF
)

echo
echo "Done. Guardrail hooks are now active for this repo (git config core.hooksPath .githooks)."
echo
echo "To get 'fleet' / 'squad' / 'check-guardrails' as shell commands, add this to"
echo "your ~/.bashrc or ~/.zshrc:"
echo
echo "$RC_SNIPPET"
echo

if [[ ! -t 0 ]]; then
  echo "(non-interactive shell — skipping the append prompt; copy the snippet above manually.)"
  exit 0
fi

read -r -p "Append it to \$HOME/.bashrc now? [y/N] " reply || true
if [[ "${reply:-N}" =~ ^[Yy]$ ]]; then
  printf '\n%s\n' "$RC_SNIPPET" >> "$HOME/.bashrc"
  echo "Appended to \$HOME/.bashrc — run 'source ~/.bashrc' or open a new shell."
else
  echo "Skipped. Copy the snippet above manually whenever you're ready."
fi
