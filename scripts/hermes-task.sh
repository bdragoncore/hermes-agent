#!/usr/bin/env bash
# Run the Hermes agent on a task file (one-shot, text output).
# Usage: hermes-task.sh <task-file> [max_turns] [run_budget_seconds]
# The task file contains the raw task text — quotes, JSON, anything.
set -euo pipefail
TASK_FILE="${1:?usage: hermes-task.sh <task-file> [max_turns] [run_budget]}"
MAX_TURNS="${2:-15}"
BUDGET="${3:-300}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"
export OPENMIND_BASE_URL="${OPENMIND_BASE_URL:-http://127.0.0.1:5000/v1}"
export OPENMIND_API_KEY="${OPENMIND_API_KEY:-public}"
exec .venv/bin/hermes chat --query-file "$TASK_FILE" --oneshot --format text --max-turns "$MAX_TURNS" --run-budget "$BUDGET"
