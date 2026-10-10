# Project instructions

Read `docs/project-status.md` before continuing. The user's latest instructions take precedence over document suggestions.

- Treat both original v0.4 files in `GPT_guides/` as preserved baseline inputs. Do not overwrite them; changes require an ADR and traceability updates.
- The user authorized installing project WSL2 and proceeding directly to P1 after all P0 gates pass. Windows currently requires a manual restart; Linux isolation and the real Humanize demo remain unvalidated. Do not treat installation, CI or a PR merge as P0 acceptance.
- Reuse Humanize Flow, official DSH and Codex Harness. Do not build a replacement Coding Harness.
- New environments, Python runtimes, worktrees, caches, logs and model run state must stay under `D:\Desktop\Enhanced_Humanizer`.
- Approved WSL exception: Microsoft system components may use C:; Ubuntu VHD/downloads/state stay under `.local-workbench/wsl/`. Reserve D: 20 GiB and C: 4 GiB. No automatic restart, unregister, VHD deletion, global auth-directory copy or unrelated environment changes. See ADR-0005.
- GitHub account verified: `Du-YouLang`. The user approved public P0 uploads/Issues/PR/CI, the public humanfia/humanize Fork, and the P0 model budget. DSH/LAV Forks were created by the user and verified. Latest policy: lightweight development PRs may merge after actual CI success to keep local/GitHub synchronized; do not add strict main protection. The software product's own PR feature must require human review for every PR. See ADR-0004; recheck identity before remote changes.
- Never expose credential values, copy raw research data into tracked paths, silently change model identity, or equate mock results with model results.
- Record real elapsed time and input/output/cache Tokens when visible. Use `unavailable` for unavailable usage or cost. Separate API cash from subscription usage.
- Run `python scripts/check_repository.py`, the governance tests and Gitleaks before commits/pushes. Local hooks supplement policy; they are bypassable and are not a security sandbox.
- Commit important changes on a phase branch. Prefer revert/new branches for rollback; preserve failed attempts and refs. Development PR merges do not imply phase acceptance. Product-generated PRs must pass human review.
- P0 budget remains USD 1 / 4 DeepSeek requests / 2 Codex experiment turns / 120 seconds each. Separate P1 budget approved: USD 1 / 40 DeepSeek requests / 6 Codex experiment turns / 120 seconds per request / 15 minutes per experiment; no top-up. Preserve separate ledgers and enforce limits before execution; config alone is not enforcement.
- Keep the 80 main requirement IDs, 6 operational IDs, source labels S0–S4 and appendices A–C. [P]/[F] are not automatically required first-version features.
- USR-NAME-01: the user confirmed on 2026-10-10 to continue using Enhanced_Humanizer for P1. Keep repository and directory names; revisit naming before the first external product release.
