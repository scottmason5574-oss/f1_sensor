---
id: circle-of-doom-start-prompt
title: Circle of Doom Phase 1 start prompt
description: Circle of Doom Phase 1 start prompt for F1 Sensor.
---

# Circle of Doom Phase 1 start prompt

Use this prompt once Phase 1 has been approved.

> Work in scottmason5574-oss/f1_sensor on a feature branch. Use the fork as the sole writable remote and review upstream read-only. Read the repository instructions and the Circle of Doom source of truth, audit, readiness matrix and plan. Confirm the working revision and scope.
>
> Execute Phase 1 only. Establish the event-time contract for gap sign and anchor, lap deficits, lap completion, track status, freshness and source/generation transitions. Trace existing TimingData, TimingAppData, TrackStatus and analysis interfaces through live, Live Delay and replay. Build reduced representative fixtures and test cold seek, linear playback, sparse data, corrections and incomplete observations. Add only contract adapters demonstrated necessary. Record coverage gaps and report whether the basic circle can use existing observations. Leave rendering, predictions and later phases for separate approval. If publishing, verify head and base both belong to the fork and leave the PR unmerged.

See the [Phase 1 plan](./CIRCLE_OF_DOOM_IMPLEMENTATION_PLAN.md).
