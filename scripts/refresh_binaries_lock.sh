#!/usr/bin/env bash
# Trigger update-binaries-lock.yml on GitHub, watch the matrix run live,
# and surface the auto-generated PR URL when it opens.
#
# Usage:
#   scripts/refresh_binaries_lock.sh
#   scripts/refresh_binaries_lock.sh "After upstream Vina v1.2.6 bump"
#
# Prereqs:
#   - gh CLI installed and authed (you already have this)
#   - `make ci` doesn't need to pass — the workflow is independent
#
# What this script does end to end:
#   1. Triggers the update-binaries-lock workflow via gh CLI.
#   2. Polls until the new run shows up in `gh run list`.
#   3. Streams the live logs (gh run watch).
#   4. After the matrix completes, finds the PR that
#      peter-evans/create-pull-request opened against `chore/update-
#      binaries-lock` and prints the PR URL.
#   5. Optionally opens it in the browser if BROWSER=1 is set.

set -euo pipefail

REPO="ArioMoniri/pinsilico"
WORKFLOW="update-binaries-lock.yml"
BRANCH_NAME="chore/update-binaries-lock"
REASON="${1:-Manual refresh from refresh_binaries_lock.sh}"

# --- preflight --------------------------------------------------------
command -v gh >/dev/null 2>&1 || {
    echo "ERROR: gh CLI not found. Install: brew install gh" >&2
    exit 1
}
gh auth status >/dev/null 2>&1 || {
    echo "ERROR: gh not authenticated. Run: gh auth login" >&2
    exit 1
}

# --- trigger the workflow ---------------------------------------------
echo "==> triggering ${WORKFLOW}"
echo "    reason: ${REASON}"
gh workflow run "${WORKFLOW}" \
    --repo "${REPO}" \
    --field "reason=${REASON}"

# gh workflow run returns immediately — wait for GitHub to register the
# new run, otherwise `gh run list` returns the previous one.
echo "==> waiting for the run to register (5 s)"
sleep 5

# --- locate the new run -----------------------------------------------
# The newest run for this workflow on this branch is ours.
RUN_ID="$(
    gh run list \
        --repo "${REPO}" \
        --workflow "${WORKFLOW}" \
        --limit 1 \
        --json databaseId,status \
        --jq '.[0].databaseId'
)"
if [ -z "${RUN_ID}" ]; then
    echo "ERROR: couldn't find the new run. Check Actions tab manually:" >&2
    echo "  https://github.com/${REPO}/actions/workflows/${WORKFLOW}" >&2
    exit 1
fi
echo "==> run id: ${RUN_ID}"
echo "    web:    https://github.com/${REPO}/actions/runs/${RUN_ID}"

# --- watch -------------------------------------------------------------
echo "==> streaming live logs (Ctrl-C to detach — the run keeps going)"
gh run watch "${RUN_ID}" --repo "${REPO}" --exit-status || {
    CONCLUSION="$(
        gh run view "${RUN_ID}" --repo "${REPO}" --json conclusion --jq .conclusion
    )"
    echo "" >&2
    echo "==> run finished with conclusion: ${CONCLUSION}" >&2
    echo "    view logs at: https://github.com/${REPO}/actions/runs/${RUN_ID}" >&2
    if [ "${CONCLUSION}" != "success" ]; then
        exit 1
    fi
}

# --- locate the PR -----------------------------------------------------
echo ""
echo "==> looking for the auto-generated PR on branch ${BRANCH_NAME}"
# peter-evans/create-pull-request may have already merged a previous run
# into the same branch; we just want whatever's open right now.
PR_URL="$(
    gh pr list \
        --repo "${REPO}" \
        --head "${BRANCH_NAME}" \
        --state open \
        --json url \
        --jq '.[0].url // empty'
)"

if [ -z "${PR_URL}" ]; then
    echo "no open PR found on ${BRANCH_NAME}." >&2
    echo "This means either:" >&2
    echo "  - the workflow ran but the merge job's diff was empty (every" >&2
    echo "    OS's hashes were already current), so no PR was needed, OR" >&2
    echo "  - the create-pull-request step failed silently — check the" >&2
    echo "    merge job logs at the run URL above." >&2
    exit 0
fi

echo "==> PR opened:"
echo "    ${PR_URL}"

if [ "${BROWSER:-0}" = "1" ]; then
    open "${PR_URL}"
fi
