# Project instructions

Read `docs/project-status.md` before continuing. The user's latest instructions take precedence over document suggestions.

- Treat both original v0.4 files in `GPT_guides/` as preserved baseline inputs. Do not overwrite them; changes require an ADR and traceability updates.
- Current scope is P0 only. Do not enter P1 without P0 acceptance and the user's direction.
- Reuse Humanize Flow, official DSH and Codex Harness. Do not build a replacement Coding Harness.
- New environments, Python runtimes, worktrees, caches, logs and model run state must stay under `D:\Desktop\Enhanced_Humanizer`.
- GitHub account verified: `Du-YouLang`. The user approved public P0 uploads/Issues/PR/CI, the public humanfia/humanize Fork, and the P0 model budget. DSH/LAV Forks were created by the user and verified. Latest policy: lightweight development PRs may merge after actual CI success to keep local/GitHub synchronized; do not add strict main protection. The software product's own PR feature must require human review for every PR. See ADR-0004; recheck identity before remote changes.
- Never expose credential values, copy raw research data into tracked paths, silently change model identity, or equate mock results with model results.
- Record real elapsed time and input/output/cache Tokens when visible. Use `unavailable` for unavailable usage or cost. Separate API cash from subscription usage.
- Run `python scripts/check_repository.py`, the governance tests and Gitleaks before commits/pushes. Local hooks supplement policy; they are bypassable and are not a security sandbox.
- Commit important changes on a phase branch. Prefer revert/new branches for rollback; preserve failed attempts and refs. Development PR merges do not imply phase acceptance or permission to start P1. Product-generated PRs must pass human review.
- Keep the 80 main requirement IDs, 6 operational IDs, source labels S0–S4 and appendices A–C. [P]/[F] are not automatically required first-version features.
- Reminder USR-NAME-01: Enhanced_Humanizer is provisional. Confirm naming with the user after P0, before P1; keep the current name until a decision is recorded.
