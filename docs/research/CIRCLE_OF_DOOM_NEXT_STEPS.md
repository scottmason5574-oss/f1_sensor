---
id: circle-of-doom-next-steps
title: Circle of Doom next steps
description: Circle of Doom next steps for F1 Sensor.
---

# Circle of Doom next steps

M1C replay and reference-lap contracts passed synthetic runtime validation. M1D found useful processed historical corroboration and established no new implementation defect. Original F1 race TimingData semantics remain unverified. [M1C validation](./CIRCLE_OF_DOOM_M1C_VALIDATION_REPORT.md), [M1D timing evidence](./CIRCLE_OF_DOOM_M1D_TIMING_EVIDENCE.md), [M1D historical cross-check](./CIRCLE_OF_DOOM_M1D_HISTORICAL_CROSSCHECK.md).

- The basic circle, physical/circular control, shared focus, unavailable states and stationary radial finish line at 12 o’clock are implemented. Physical remains the default.
- The synthetic calculation foundation wraps moving leader phase clockwise from a verified crossing at the finish line and places eligible same-lap followers behind that phase using verified gaps. Numeric driver markers remain disabled. [Owner-confirmed specification](https://github.com/scottmason5574-oss/f1_sensor/issues/7).
- Authentic crossing anchoring, certified reference durations, real-time motion, lapped residual placement and authoritative replay transitions remain open. A future race observation requires separate owner approval. [M1D readiness decision](./CIRCLE_OF_DOOM_M1D_READINESS_DECISION.md).

## Parked live transport work

M2-2A-6B-1 stopped at transport eligibility. The installed aiohttp client accepted masked server frames and lacked a no-redirect option on its WebSocket upgrade path. The approved websockets 17.4 release was installed in an isolated research environment. Synthetic byte probes showed that it accepted nonminimal wire-frame length encodings. No live bridge was implemented and no authentic timing data was collected. Future work requires separate approval for a compliant transport or bounded parser approach.

The [implementation plan](./CIRCLE_OF_DOOM_IMPLEMENTATION_PLAN.md) records Phase 2 exit criteria.
