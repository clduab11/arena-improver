#!/usr/bin/env bash

set -euo pipefail

WORKFLOW_NAME="sync-to-hf.yml"
REF="${1:-main}"

if ! command -v gh >/dev/null 2>&1; then
	echo "[hf-sync] GitHub CLI (gh) is required. Install it from https://cli.github.com/" >&2
	exit 1
fi

echo "[hf-sync] Triggering $WORKFLOW_NAME on ref '$REF'..."
gh workflow run "$WORKFLOW_NAME" --ref "$REF"

# Give GitHub a moment to enqueue the run so that we can watch it
sleep 5

RUN_ID=$(gh run list --workflow="$WORKFLOW_NAME" --branch="$REF" --limit 1 --json databaseId -q '.[0].databaseId')

if [[ -z "$RUN_ID" || "$RUN_ID" == "null" ]]; then
	echo "[hf-sync] Workflow queued but no run ID was returned. Check https://github.com/${GITHUB_REPOSITORY:-clduab11/vawlrathh}/actions manually."
	exit 0
fi

echo "[hf-sync] Watching run $RUN_ID..."
gh run watch "$RUN_ID"

echo "[hf-sync] Latest logs:"
gh run view "$RUN_ID" --log
