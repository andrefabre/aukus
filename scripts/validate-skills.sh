#!/usr/bin/env bash
# validate-skills.sh — check every .claude/skills/*/SKILL.md has valid,
# complete YAML frontmatter (name, description, version). Used by the
# pre-commit hook and can be run standalone for full-repo verification
# (Task 3 of the framework bootstrap: "verify SKILL.md frontmatter is valid").
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAIL=0

check_file() {
  local file="$1"
  local frontmatter
  frontmatter="$(awk '/^---$/{n++; next} n==1' "$file")"

  if [[ -z "$frontmatter" ]]; then
    echo "FAIL $file: no YAML frontmatter block found"
    FAIL=1
    return
  fi

  local name description version
  name="$(echo "$frontmatter" | sed -n 's/^name: *//p' | head -1)"
  description="$(echo "$frontmatter" | sed -n 's/^description: *//p' | head -1)"
  version="$(echo "$frontmatter" | sed -n 's/^version: *//p' | head -1)"

  local ok=1
  if [[ -z "$name" ]]; then echo "FAIL $file: missing 'name'"; ok=0; fi
  if [[ -z "$description" ]]; then echo "FAIL $file: missing 'description'"; ok=0; fi
  if [[ -z "$version" ]]; then echo "FAIL $file: missing 'version'"; ok=0; fi
  if [[ -n "$description" && ${#description} -lt 20 ]]; then
    echo "FAIL $file: 'description' too short to be a useful trigger (${#description} chars)"
    ok=0
  fi

  local dirname_expected
  dirname_expected="$(basename "$(dirname "$file")")"
  if [[ -n "$name" && "$name" != "$dirname_expected" ]]; then
    echo "FAIL $file: name '$name' does not match directory '$dirname_expected'"
    ok=0
  fi

  if [[ "$ok" -eq 1 ]]; then
    echo "OK   $file"
  else
    FAIL=1
  fi
}

shopt -s nullglob
files=("$ROOT"/.claude/skills/*/SKILL.md)
if [[ ${#files[@]} -eq 0 ]]; then
  echo "No SKILL.md files found under .claude/skills/"
  exit 1
fi

for f in "${files[@]}"; do
  check_file "$f"
done

exit "$FAIL"
