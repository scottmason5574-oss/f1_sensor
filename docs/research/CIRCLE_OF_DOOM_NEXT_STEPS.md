---
id: circle-of-doom-next-steps
title: Circle of Doom next steps
description: Circle of Doom next steps for F1 Sensor.
---

# Circle of Doom next steps

1. Obtain approval for Phase 1. Check the fork revision, repository guidance and working tree.
2. Trace representative replay fixtures and source timestamps for gaps, lap completion, lapped transitions, timing resets and TrackStatus. Document which cases require live confirmation.
3. Compare straight playback with cold seek and Live Delay release for the same race instant. Identify gaps in replay coverage, reconnect warm-up and freshness metadata.
4. Decide whether a green-lap reference can use current observations. Propose the smallest bounded extension only for proven gaps. Defer precise crossings until their evidence improves.
5. Report the field contract, test evidence and readiness decision before starting the circle renderer.

See the [implementation plan](./CIRCLE_OF_DOOM_IMPLEMENTATION_PLAN.md) for exit criteria. Later investigations should prioritize stop-to-lap alignment and held-out rejoin validation. MultiViewer overlay parity can proceed separately if runtime evidence becomes available.
