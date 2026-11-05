---
id: circle-of-doom-next-steps
title: Circle of Doom next steps
description: Circle of Doom next steps for F1 Sensor.
---

# Circle of Doom next steps

## Current status

Research and architecture, Phase 1 timing and replay foundations, and Phase 2 basic circular mapping with opt-in estimated positioning are complete. Phase 3 is planned. See the [implementation plan](./CIRCLE_OF_DOOM_IMPLEMENTATION_PLAN.md) for the timing and positioning contract.

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

[Phase 3 — Straight-line pit window](./CIRCLE_OF_DOOM_IMPLEMENTATION_PLAN.md#phase-3--straight-line-pit-window) is planned. It will show an estimated pit loss with provenance, the selected driver and nearby traffic, and the expected rejoin position and potential rank range. Both map views will use the same calculation and report uncertainty or unavailable inputs. The calculation must respect live, delayed and replay timing boundaries.

Before implementation, confirm which Phase 2 selection and timing fields can supply a coherent snapshot, and agree on acceptable pit-loss provenance and fallback behavior. Keep live verification open as a prerequisite for relying on live predictions.

**Proposed first development task.** Trace those inputs through the three timing modes and define a shared prediction contract using deterministic fixtures for a supported estimate, unavailable loss and uncertain traffic. Review the contract before wiring either renderer.
