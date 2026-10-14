"""Prospective request output policy; never changes old phase defaults."""

OUTPUT_REVISION='USER_APPROVED_2026-10-12_DSH_DEFAULT256000'
MAIN_OUTPUT_TOKENS=256000

# The same process guidance is given to every coding role, including Codex.
# Checkpoints are ordinary task files, not a second agent/harness or automatic
# replay of a failed run. Existing protected-file rules still apply.
GENERATION_GUIDANCE=(
    'Work in small independently verifiable steps. Keep each model reply and tool '
    'argument small; do not generate a large complete file in a single call. '
    'Use small targeted patches or write a large NEW file in checked chunks. '
    'Persist completed work in the workspace after each step, and verify files '
    'after writing them. Inspect the current workspace before proceeding, '
    'including any inherited partial work; do not repeat completed steps. '
    'Run relevant public checks and commit the implementation with a clean '
    'worktree. Finish with a short summary, file paths and unresolved issues. '
    'These instructions never authorize changing protected original tests, '
    'fixtures, dependencies or hidden acceptance criteria.'
)
