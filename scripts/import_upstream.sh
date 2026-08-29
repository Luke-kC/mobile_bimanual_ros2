#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p "$ROOT/src"
cd "$ROOT"

if [[ -s "$ROOT/upstream.repos.lock" ]]; then
    MANIFEST="$ROOT/upstream.repos.lock"
else
    MANIFEST="$ROOT/upstream.repos"
fi

echo "Importing upstream dependencies from $(basename "$MANIFEST")"
vcs import src <"$MANIFEST"
