---
id: circle-of-doom-next-steps
title: Circle of Doom next steps
description: Circle of Doom next steps for F1 Sensor.
---

# Circle of Doom next steps

## Current status

Research and architecture, Phase 1 timing and replay foundations, and Phase 2 basic circular mapping with opt-in estimated positioning are complete. Phase 3.1–3.4A synthetic foundations and the standalone preview merged in PRs #12–16 through main `efccd191bc0d4adbc8af5f4ca5d2c38c18c6ab35`. Production pit-window integration remains pending. The owner authorized [Phase 3.4B Task 1 only](./CIRCLE_OF_DOOM_PHASE3_4B_AVAILABILITY.md): a pure availability decision boundary and milestone reconciliation, submitted for separate acceptance. Tasks 2–5 remain unauthorized. See the [implementation plan](./CIRCLE_OF_DOOM_IMPLEMENTATION_PLAN.md) for the timing and positioning contract.

[PR #10](https://github.com/scottmason5574-oss/f1_sensor/pull/10) merged into `main` as [372b03a7737fb0ec6f7f1ec588e74202178e04a7](https://github.com/scottmason5574-oss/f1_sensor/commit/372b03a7737fb0ec6f7f1ec588e74202178e04a7). Its final head was [62f763f4b6f43764f0c0eda1c4892f85fe011a2f](https://github.com/scottmason5574-oss/f1_sensor/commit/62f763f4b6f43764f0c0eda1c4892f85fe011a2f). The final head and Unraid candidate [10289ad](https://github.com/scottmason5574-oss/f1_sensor/commit/10289ad) have identical integration trees.

## Phase 2 acceptance evidence

The owner reported seven successful checks on the Unraid Home Assistant test installation.

1. Cars appeared after usable timing data arrived.
2. Cars moved smoothly between updates.
3. Leaving the dashboard and returning preserved replay and recovered driver markers.
4. Pausing replay stopped the cars.
5. Seeking to another lap recovered positioning once fresh evidence arrived.
6. The roster followed race classification order.
7. The Physical Track Map continued to work.

The final integration also passed 44 focused tests in Ubuntu WSL using a Home Assistant test instance and fixtures. Those tests covered the installed integration lifecycle, authenticated WebSocket behavior, delayed timing, replay seek and reload.

## Accepted validation exception

The owner approved merging PR #10 with incomplete standalone runtime evidence under the existing `AGENTS.md` criteria. Final user-facing acceptance ran on Unraid. The originally designated standalone Ubuntu WSL instance was not used for final acceptance.

Before relying on live-race positioning, record installed-file parity, config-entry load and runtime logs on the designated standalone instance. Verify authenticated analysis snapshot and timestamped TimingData delivery, Live Delay release, replay reset and generation changes, and live/replay source isolation. The focused fixture tests and Unraid checks provide separate evidence for their covered scenarios. Original F1 race timing semantics, certified crossing and lap duration evidence, and lapped residual placement remain unverified. The card labels timing-derived positions **Estimated** and leaves placement unavailable when evidence is insufficient. See the [M1D readiness decision](./CIRCLE_OF_DOOM_M1D_READINESS_DECISION.md).

The independent live transport investigation stopped at transport eligibility. Synthetic probes found that aiohttp accepted masked server frames and lacked a no-redirect upgrade option, and that websockets 17.4 accepted nonminimal frame length encodings. No bridge or authentic capture resulted. Any resumed transport or live capture work requires separate approval. See the [timing validation plan](./CIRCLE_OF_DOOM_M2_TIMING_VALIDATION_PLAN.md).

## Phase 3 handoff

[Phase 3 — Straight-line pit window](./CIRCLE_OF_DOOM_IMPLEMENTATION_PLAN.md#phase-3--straight-line-pit-window) has pure input validation, hypothetical displacement, lap-aware coordinates, rejoin ranking and an isolated synthetic straight-line preview. The [research index](./CIRCLE_OF_DOOM_RESEARCH_INDEX.md) links their contracts and limitations. Neither production map consumes these additions; no real pit-loss estimate is approved.

Before any production integration, review authentic timing joins, complete-grid evidence, approved loss provenance, localization and production scope. Keep live verification open as a prerequisite for relying on live predictions. Task 1 authorization adds no panel, subscription, adapter, backend transport, calibration or prediction consumer. Mathematical availability, declared evidence completeness and approved real-race prediction are separate decisions. The Task 1 boundary always refuses production prediction approval.

## Approved one-time Phase 3 foundation runtime-evidence exception

The repository owner approved this separate, one-time exception on **November 5, 2026**, independently of the accepted PR #10 exception. It does not claim that missing runtime checks passed. It applies only to the reviewed PR #12–16 heads: `38ced917`, `844c5a65`, `a0d9039a`, `1732bb3c` and `897c84e5`, with the documentation handoff in PR #11 at `737472ed`.

The approved exception permits merging this isolated foundation without new installed-source parity, config-entry load, authenticated HA snapshots, delayed timing/replay-generation observations or runtime-log evidence. Its justification is that the mathematical helpers and synthetic preview have no production consumers. Existing Circle of Doom and Physical Track Map behavior is unchanged; only unused frontend assets are added. `PIT_LOSS_FALLBACKS` remains empty, demo fixtures are excluded from release artifacts, and no real-circuit prediction is enabled.

Combined-source release verification and a conflict-free merge rehearsal passed separately from runtime validation. Current hosted selected checks pass, including HACS/hassfest for #12–16. These results do not establish HA runtime activation or real-race accuracy. Required CI, package/security checks and application safety checks remain blocking; the exception does not excuse failures or authorize deployment.

Any change to these heads or production isolation requires renewed review. Any future live/replay adapter, production consumer, prediction enablement or Phase 3.4B integration requires its own authorization and applicable runtime validation, including source parity, timing availability, reset/seek/correction and generation isolation. This exception grants no continuing waiver.

## Approved merge and publication scope

On November 5, 2026, the owner explicitly approved this Phase 3 exception and the expected documentation publication and normal draft-release workflow for merging PRs #11-16 and this handoff. Required verification remains blocking. Pushes to main trigger exact-commit verification, documentation publication/Context7 refresh, and release verification that may create or recover a draft release when its gates and versioning conditions permit. Release publication remains manual. Repository workflows do not automatically deploy to Home Assistant or Unraid. No workflow behavior is suppressed by this exception.

The foundation merges are complete. Their historical procedure used merge commits and sequential retargeting to preserve reviewed ancestry. Future PR verification must establish the actual runner checkout, head/base pair and tested tree; editing a base alone does not trigger fresh product CI.

## Landed foundation and final-source evidence

| Phase / PR | Reviewed head | Main merge SHA |
| --- | --- | --- |
| 3.1 / #12 | 38ced917 | fa50e14d8b19d4bec9c3410c3c5cf1951b200f18 |
| 3.2B / #13 | 844c5a65 | 3360c1f210ce8ff65c534c1a50133bc7a4e87c9d |
| 3.3A / #14 | a0d9039a | 14646402bc30fb1ee91b3b6244061dfd79f75cc1 |
| 3.3B / #15 | 1732bb3c | a6fed81ce4ddce959c9b3f8e3161014cc0a0e8e2 |
| 3.4A / #16 | 897c84e5 | efccd191bc0d4adbc8af5f4ca5d2c38c18c6ab35 |

Final main tree `ff62913c6f9cf2c4c772dc6a92eee4e94e953f0b` equals the verified #16 proposed-merge tree. The retained local full-main receipt has source fingerprint `fb8fc2f144e5305e16fb8ba01ef597a8cdeb1db40929b1131ae4ea3ec0d70113`; all eight selected groups passed. That receipt describes its recorded tools, dependencies and source, not a new verification of later changes.

[Final exact-SHA release verification 42150630084](https://github.com/scottmason5574-oss/f1_sensor/actions/runs/42150630084) succeeded on attempt 2. Product, HACS/hassfest, package, documentation and security passed on attempt 1. Its release job initially failed a read-only contributor lookup before asset handling; one targeted retry after endpoint revalidation succeeded. Matching tagged v1.3.0 draft assets were preserved, and no new software version was published.

[Final documentation publication 42150629466](https://github.com/scottmason5574-oss/f1_sensor/actions/runs/42150629466) succeeded, including actual Pages deployment pinned to stable `efccd191` and beta `55ca2a45`. Context7 failed advisory-only. Documentation publication and draft recovery are separate from product verification, HA runtime activation and real-race accuracy. Existing releases remained drafts; the historical v1.3.0 package was not relabeled as the new foundation source.

## Historical verification limitations

The original release run [42128380241](https://github.com/scottmason5574-oss/f1_sensor/actions/runs/42128380241) failed at a release-asset DELETE. The old wrapper discarded stderr and HTTP status. The cause remains **HTTP unknown / unclassified CLI API failure**; neither permissions, authentication nor a server fault can be inferred. No destructive reproduction was performed. Later idempotent draft recovery and byte-for-byte asset audits passed, without reconstructing the missing historical status.

PR #14 native pre-merge run `42145946681` actually checked out stale `81cce7e`, not intended `fc38f074`. Failing to inspect the runner checkout before merging was an agent verification oversight: the pre-merge exact-source requirement was missed. [Exact-SHA post-merge verification 42147024582](https://github.com/scottmason5574-oss/f1_sensor/actions/runs/42147024582) subsequently passed. PRs #15 and #16 used explicit trusted dispatch with checkout proof (`4c7dbf9` and `2607597` respectively), and final-main checks passed. Those later checks remain valid; they do not retroactively make #14's pre-merge sequence compliant.

The foundation reports retain historical statements about open/unmerged PRs at authorship. This handoff is the current milestone record. No foundation CI, synthetic fixture or owner exception supplies the authentic timing joins, calibrated net-loss range, complete roster, runtime evidence or separate approval required for real predictions.
