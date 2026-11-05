---
id: circle-of-doom-next-steps
title: Circle of Doom next steps
description: Circle of Doom next steps for F1 Sensor.
---

# Circle of Doom next steps

## Current status

Research and architecture, Phase 1 timing and replay foundations, and Phase 2 basic circular mapping with opt-in estimated positioning are complete. Phase 3.1–3.4A synthetic foundations and the standalone preview are implemented in unmerged PRs #12–16. Production pit-window integration remains pending. See the [implementation plan](./CIRCLE_OF_DOOM_IMPLEMENTATION_PLAN.md) for the timing and positioning contract.

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

Before Phase 3.4B, review authentic timing joins, complete-grid evidence, approved loss provenance, localization and production integration scope. Keep live verification open as a prerequisite for relying on live predictions. Phase 3.4B is not authorized by this handoff.

## Proposed Phase 3 runtime-evidence exception — owner approval pending

The repository owner approved this separate, one-time exception on **November 5, 2026**, independently of the accepted PR #10 exception. It does not claim that missing runtime checks passed. It applies only to the reviewed PR #12–16 heads: `38ced917`, `844c5a65`, `a0d9039a`, `1732bb3c` and `897c84e5`, with the documentation handoff in PR #11 at `737472ed`.

The approved exception permits merging this isolated foundation without new installed-source parity, config-entry load, authenticated HA snapshots, delayed timing/replay-generation observations or runtime-log evidence. Its justification is that the mathematical helpers and synthetic preview have no production consumers. Existing Circle of Doom and Physical Track Map behavior is unchanged; only unused frontend assets are added. `PIT_LOSS_FALLBACKS` remains empty, demo fixtures are excluded from release artifacts, and no real-circuit prediction is enabled.

Combined-source release verification and a conflict-free merge rehearsal passed separately from runtime validation. Current hosted selected checks pass, including HACS/hassfest for #12–16. These results do not establish HA runtime activation or real-race accuracy. Required CI, package/security checks and application safety checks remain blocking; the exception does not excuse failures or authorize deployment.

Any change to these heads or production isolation requires renewed review. Any future live/replay adapter, production consumer, prediction enablement or Phase 3.4B integration requires its own authorization and applicable runtime validation, including source parity, timing availability, reset/seek/correction and generation isolation. This exception grants no continuing waiver.

## Approved merge and publication scope

On November 5, 2026, the owner explicitly approved this Phase 3 exception and the expected documentation publication and normal draft-release workflow for merging PRs #11�16 and this handoff. Required verification remains blocking. Pushes to main trigger exact-commit verification, documentation publication/Context7 refresh, and release verification that may create or recover a draft release when its gates and versioning conditions permit. Release publication remains manual. Repository workflows do not automatically deploy to Home Assistant or Unraid. No workflow behavior is suppressed by this exception.

Use merge commits to preserve ancestry in order #11, #12, #13, #14, #15, #16. Before merging #12, retarget draft #13 to main; before merging #13 retarget #14, and repeat through #16. This avoids merged-parent branch cleanup removing a dependent base. After each parent lands, recheck the child's diff, ancestry and fresh proposed-merge verification against main before merging it. Base editing alone does not trigger product CI; use the authorized ready-for-review transition or explicit verification dispatch. Current per-PR checks do not validate those future merge results.
