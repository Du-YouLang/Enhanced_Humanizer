# P6: continuation after requested shutdown

The user requested shutdown at 08:15 on 2026-10-13 and subsequently explicitly
requested continuation. The original main controller, its scientific descendants
and the recovery supervisor were stopped. Auto recovery and the 45-minute heartbeat
were paused. The authoritative shutdown checkpoint and both old batch indexes remain.

At restart, 11 distinct v12-final2 tasks and their separate trace-sensitivity runs
were complete; this count includes model failures and does not mean 11 tasks passed.
PC-ALM had finished every model role, judging and selection. Five acceptance files
(DS0, A, B, C, M) had completed. A late D receipt explicitly reports InterruptedError
from signal 15 within the recorded shutdown interval, not a scientific failure.
The exact old D file is retained, excluded from failure counting and superseded only
by a separate numerical continuation file. Black-5 remains INFRA_RETRY_PENDING;
no complete or partial coding task is replayed.

Supplemental entry `scripts/continue_p6_acceptance_linux.py` and ADR-0029 establish
acceptance-only continuation outside the immutable main deployment. Native checks
verified every original candidate's full patch/worktree evidence, source mapping,
public pool, selection hash, prompt and environment. Six frozen result schemas
were checked without writing results or invoking a provider. A real fenced JAX
operation returned cuda:0 and [2, 3] on the local GPU. The unchanged network fence
returned HTTP 200 from the official routing probe on its first attempt. The ledger
remained byte-identical through all checks.

The corrected private preparation is
`/opt/workbench/recovery/p6-acceptance-20261013-v2/state/plan.json`, SHA
752ed417f2c3f1d14fa8246b97f3164268c873871fc15aa53be46477bfcbf9e0.
The initial preparation made zero model calls and remains preserved. Windows local
runtime p6-boot-v7 keeps the complete v6 journal prefix and cumulative ledger floor.
It guards the acceptance controller before dispatching any new model stage. Unexpected
same-boot exits and missing ownership receipts require inspection rather than retry.
New boot recovery skips completed acceptance files and never regenerates candidates.

Actual acceptance-only continuation started at 09:33:40 Beijing. The native owner is
GNU timeout PID 359, start ticks 5100, boot a05710f9-10e9-40f5-9076-6be235299bed;
its Python controller is 360. An independent descendant snapshot showed live
scientific worker activity (214 CPU ticks in a two-second interval) and a D grading
start bound to the original program identity. All original input files and the
budget ledger remained unchanged. This is execution evidence, not PC-ALM acceptance.

Windows supervisor PID 11040 owns the 30-second loop. HKCU user-login registration
points only to the v7 windowless Python runtime; the old v6 registration was explicitly
disabled first. The authorized 45-minute heartbeat is ACTIVE again. No shutdown or
automatic model replay was performed. After acceptance completes and its controller
exits, only the missing PC-ALM sensitivity and unstarted SCI-STROKE, SCI-EGL and
SCI-GRANGER-GPU stages can run serially. Original per-arm monotonic intervals lost
at shutdown are unavailable and excluded from timing comparisons.

Functional commit 2617d425c7bb32eca78f36d32d749b86abd7e150 was pushed to the existing
development PR #37. Exact CI run 38332589366 reports integrity, secrets and linux-budget
SUCCESS. Local Windows full tests before the final signal-exclusion test were 202
tests with seven platform skips; the final nine acceptance controls, 33 recovery
controls, seven governance controls and Gitleaks passed. The CI executed the final
source. A pinned private CI receipt guards any subsequent paid continuation.

Cumulative budget at restart: 4899 DeepSeek requests, 154 subscription experiment
turns, API upper bound USD85.7703858. Actual cash is unavailable. Byte SHA remains
74ab7a7a41c3e9e41cf2074247ce1e0867470ae6ac4e47f2f80f7101ee39446e.
The remaining approved API upper-bound budget is USD14.2296142 and 5101 requests,
subject to every existing request/role/cumulative guard. No balance is reset or
carried from closed phase ledgers.

Full P6 and live Pi comparison remain unaccepted. Existing exact P7 local-preview
receipts remain valid for their own source versions; this audit does not establish
a new package installation. Product Draft #30 awaits human merge and external
release still needs human confirmation.
