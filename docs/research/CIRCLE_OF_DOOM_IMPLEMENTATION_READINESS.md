---
id: circle-of-doom-implementation-readiness
title: Circle of Doom implementation readiness
description: Circle of Doom implementation readiness for F1 Sensor.
---

# Circle of Doom implementation readiness

Phase 1 validation is partial. Later phases depend on the evidence and tests below.

| Feature | Existing support | Backend need | Frontend and calculation | Tests and dependencies | Readiness and unknowns |
| --- | --- | --- | --- | --- | --- |
| Mode, team colors and focus | Track Map, card focus and driver metadata | None expected | Persist mode, default to physical, reuse focus | Old config, toggle, keyboard and touch | Ready to design |
| Basic circle and lap counter | Timing snapshot and lap fields | Timestamp and lap residual contract; expose missing inputs only | Reference median, gap-to-angle, lap deficit and responsive SVG | Sign, wrapping, lapping and missing GPS | Conditional on Phase 1 |
| Smooth animation | Physical replay interpolation patterns | Generation and clock alignment | Unwrap, reduced motion and seek resets | Correction, replay speed and disconnect | Conditional on clock contract |
| Timing-only fallback | Gap and lap observations | Determine freshness and formats | Provisional positions or unavailable state | Sparse frames and stale data | Conditional on timing semantics |
| Mini-sector refinement | Bounded status frames | Validated crossings and complete lap coverage if used | Optional segment progress | Status changes versus true crossing | Research required |
| Straight window and fallback | Driver selection and timing | Approved circuit estimates or unavailable | Shared loss range, traffic and confidence | Same prediction in both renderers | Conditional on Phase 2 and fallback |
| Observed loss and ghost markers | Stop, lap and strategy observations | Verify stop/lap/status joins and bounded history | Robust median, lap-aware ordering and uncertainty | Held-out stops, ties, mixed status and deduplication | Conditional on replay evidence |
| SC/VSC and red flags | TrackStatus | Ordered transitions over estimation windows | Scenario rules and confidence | Green, mixed, SC, VSC and red | Calibration required |
| Inner lane and arcs | Physical map and pit information | Confirm pit-state timestamps | Independent SVG overlays and lane transitions | Entry/exit and dense layouts | Deferred; exact overlay meanings unknown |
| Delay and replay | Existing routing and controllers | Prove coherent as-of snapshots and seek reconstruction | Consume one clock and reset on discontinuities | Cold seek, delay changes, no future leak | Cross-cutting gate |

## Phase 1 validation evidence

The [Phase 1 validation report](./CIRCLE_OF_DOOM_PHASE1_VALIDATION_REPORT.md) records the clocked live-delta path, the replay unavailable fallback, and the remaining reference-lap and verification gates. Phase 2 readiness remains conditional.
