# AGENTS.md

Instructions for any AI agent (Claude Code, GitHub Copilot CLI, or
otherwise) operating in this repository. Read this file before doing
anything else in it.

## What this repo is

The `aukus` product repo. It uses the
[agentic-workflow](https://github.com/andrefabre/agentic-workflow) framework:
modular Claude Code skills, persistent agent personas, a file-backed
multi-agent coordination layer (`.squad/`), parallel execution via GitHub
Copilot CLI's `/fleet`, and enforced git guardrails.

Product code lives in `prototype/` (DISP evidence-plumbing demo; see
`prototype/README.md`). Its tests are run with
`cd prototype && .venv/Scripts/python -m pytest -q` (or `.venv/bin/python` on
macOS/Linux). Business-case analysis is in `docs/`.

## Layout

```
.claude/
  skills/            Modular, trigger-based Claude Code skills
    tdd/                Red-green-refactor enforcement
    grill-me/           Socratic design stress-testing
    git-guardrails/     Human-approval gate for destructive git ops
    squad-delegate/     Multi-agent context handoff via .squad/
  commands/          Slash commands (/fleet-run, /squad-sync)
  agents/            Persistent personas (architect, reviewer, security-auditor)

.squad/              File-backed persistence layer for multi-agent work
  tasks/                Work queue: [TODO] / [IN_PROGRESS] / [BLOCKED] / [DONE]
  context/              Per-role current-state snapshots
  mailbox/              Self-contained handoff notes between roles
  DECISIONS.md          Append-only architectural decision log
  logs/                 bin/fleet run logs (gitignored)

bin/                  Executable CLI entry points
  fleet                 Dispatch a goal to Copilot CLI's /fleet, non-interactively
  squad                 Manage .squad/ tasks, mailbox, decisions
  check-guardrails       Dry-run of the guardrail rules the git hooks enforce

scripts/
  install-aliases.sh    One-time setup: installs .githooks, chmod +x, shell aliases
  validate-skills.sh    Validates every SKILL.md's frontmatter
  lib/guardrails.sh     Shared logic used by hooks + bin/check-guardrails

.githooks/            Guardrail hooks (enabled via core.hooksPath, not .git/hooks/
                       directly, so they're versioned and travel with clones)
  pre-commit             Blocks direct commits to main/master, broken SKILL.md,
                          shell syntax errors
  pre-push               Blocks force-push and direct push to main/master
```

## Rules for agents working in this repo

1. **Run `scripts/install-aliases.sh` before your first commit** in a
   fresh clone — hooks are not active until `core.hooksPath` is set.
2. **Follow `git-guardrails`** ([.claude/skills/git-guardrails/SKILL.md](.claude/skills/git-guardrails/SKILL.md)):
   force-push, `reset --hard`, `clean -f`, and direct pushes to
   `main`/`master` require explicit human confirmation before you
   attempt them — don't rely on the hook alone to stop you.
3. **Use `.squad/` for anything spanning more than one agent turn or
   more than one persona.** Don't keep multi-step state only in chat —
   it doesn't survive a session boundary or a handoff to another agent.
   See [.claude/skills/squad-delegate/SKILL.md](.claude/skills/squad-delegate/SKILL.md).
4. **New behavior gets a failing test first** when working in a project
   that has a test suite — see
   [.claude/skills/tdd/SKILL.md](.claude/skills/tdd/SKILL.md).
5. **Non-trivial design decisions get challenged before they're built**,
   via `/grill-me` or the `grill-me` skill, and get recorded in
   `.squad/DECISIONS.md` once made.
6. **`bin/fleet` goals must be self-contained.** Copilot CLI fleet
   subagents don't inherit this conversation — see
   [.claude/commands/fleet-run.md](.claude/commands/fleet-run.md).
7. **Don't hand-edit `.squad/tasks/` or `.squad/mailbox/` file names.**
   Use `bin/squad task add` / `bin/squad mail send` so status tags and
   naming stay consistent for anyone (agent or human) scanning the
   directory later.

## How to extend this framework

- New skill: `mkdir .claude/skills/<name>` and add `SKILL.md` with
  `name`/`description`/`version` frontmatter — run
  `scripts/validate-skills.sh` before committing.
- New persona: add `.claude/agents/<name>.md` with `name`/`description`/
  `tools`/`model` frontmatter, and give it a corresponding
  `.squad/context/<name>.md` on first use.
- New guardrail rule: add it to `scripts/lib/guardrails.sh` so both the
  hooks and `bin/check-guardrails` pick it up from one place.
