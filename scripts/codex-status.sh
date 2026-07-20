#!/usr/bin/env bash
# codex-status.sh — compact, read-only takeover context for coding agents.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

printf 'root: %s\n' "$ROOT"
printf 'branch: %s\n' "$(git branch --show-current)"
printf 'head: %s\n' "$(git log -1 --format='%h %s')"

printf '\nworking tree:\n'
git status -sb

printf '\nrecent commits:\n'
git log -5 --oneline

printf '\nprotected local files (inspect, never stage during takeover):\n'
for path in \
    AGENTS.md \
    annotations/src/main/resources/classids.properties
do
    if [[ -n "$(git status --short -- "$path")" ]]; then
        printf '  modified: %s\n' "$path"
    fi
done

printf '\nnext roadmap item:\n'
sed -n '/^### 7\.3 /,/^### 7\.4 /p' docs/ROADMAP.md | sed '$d'
