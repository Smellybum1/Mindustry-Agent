#!/usr/bin/env bash
# codex-status.sh — compact, read-only takeover context for coding agents.
set -euo pipefail

repo_git(){
    git -c core.autocrlf=true "$@"
}

ROOT="$(repo_git rev-parse --show-toplevel)"
cd "$ROOT"

printf 'root: %s\n' "$ROOT"
printf 'branch: %s\n' "$(repo_git branch --show-current)"
printf 'head: %s\n' "$(repo_git log -1 --format='%h %s')"

printf '\nworking tree:\n'
repo_git status -sb

printf '\nrecent commits:\n'
repo_git log -5 --oneline

printf '\nprotected local files (inspect, never stage during takeover):\n'
for path in \
    AGENTS.md \
    annotations/src/main/resources/classids.properties
do
    if [[ -n "$(repo_git status --short -- "$path")" ]]; then
        printf '  modified: %s\n' "$path"
    fi
done

printf '\nnext roadmap item:\n'
sed -n '/^### 8\.5 /,/^## Milestone 9:/p' docs/ROADMAP.md | sed '$d'
