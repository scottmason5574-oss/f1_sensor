---
id: circle-of-doom-phase3-4a-linear-view
title: Circle of Doom standalone straight-line preview
---

# Phase 3.4A straight-line presentation

Based on PR15 at 1732bb3c663954a6a188ffe5a242bf8294661e9a, preserving the PR14/13/12 chain. PR11 remains open/non-draft; PR12 through PR15 remain open/draft and unmerged at their inspected heads. Work is on a separate dependent branch; those branches are untouched.

## Component and isolation

`modular/pit-window-view.js` exports the reusable Lit component `f1-pit-window-view`. It accepts a Phase 3.3B result, driver identity/team/color metadata and a fallback selectedId. The pure presentation adapter lives in pit-window-presentation.js. Neither calculates ranks, subscribes, reads the wall clock or imports the ranking engine. The existing card, map, catalog, editor, default configuration and subscriptions never import this view.

The two modules are included in the existing frontend asset delivery allowlist, so their ordinary imports are available for later reviewed reuse. No production card option, card registration or automatic demo route is added. Demo fixtures and HTML live only under frontend-tests and are excluded from release artifacts. The demo is reachable through the existing development test server at /frontend-tests/pit-window-demo.html; it is not a published site or HA dashboard. Run the existing frontend test server locally to review it. The component always displays SYNTHETIC PREVIEW / NOT RACE DATA. Production integration requires a separately reviewed label/localization contract; removing that guard is outside this task.

The independent fictitious Aurora/Ember/Violet/Jade identities and synthetic frame factory are in frontend-tests/fixtures/pit-window-demo.js. They invoke the actual Phase 3.3B pure engine to produce demonstrator outputs. No real driver, circuit estimate or recorded race timing is used. A browser-native selection event is handled only by the harness, which recomputes synthetic results. No HA or replay subscriptions, new endpoints or runtime adapters exist. PIT_LOSS_FALLBACKS remains empty.

## Visual and accessibility rules

All driver lanes share one horizontal unwrapped race-time coordinate scale; further right is ahead. Separate lanes keep equal and overlapping coordinates legible without assigning rank order. No wrapped angles or inferred lap offsets are used. A selected outline, hatched interval versus solid point marks, and explicit text supplement team colors. Driver metadata falls back to racing number and an unknown-team label. Touch targets are at least 44px; native buttons support keyboard operation, pressed state and visible focus. Focus returns to the selected driver after synthetic recomputation. Plot labels expose coordinate ranges and explicit deficits to screen readers; the slot summary is a polite live region.

The view reports hypothetical ordinal slots or unresolved slot ranges only when the engine marks ranking available and coverage complete. Partial grids show eligible/expected coverage, unavailable rows and conditional neighbors. Missing source provenance suppresses slot and axis estimates even if a caller supplies a cached mathematical rank. Pit-exit and in/out-window labels remain distinct, with an explicit warning that a window estimate is not immediate exit. No midpoint is used as a predicted coordinate or slot.

Axis values and timing separation are rounded to at most one decimal with approximate labels. This is formatting, not a claim of measured accuracy. Range hatching and non-color wording preserve the uncertain/point distinction even when formatted bounds round together. Only the engine's guaranteed nearest identities are described as nearest; unknown neighbors remain not established. Positive relative separation means traffic ahead. Lap deficits remain explicit rather than being derived from the drawing.

The component reuses existing shared F1 Sensor styles, heading/font hooks and theme colors. The demo supplies its own isolated dark palette. Responsive lanes fit narrow screens without horizontal document scrolling. There is no animation or timer at any motion preference; reduced-motion rules explicitly disable transitions/animations. Forced-color rules preserve marks, borders and keyboard focus. The demo language is English only; production localization is deferred.

## Verification and visual evidence

Six presentation unit tests and nine browser tests exercise exact slots, ranges, overlap, ties, incomplete traffic, missing source, horizon labels, mobile layout, keyboard/focus, reduced motion and isolated data delivery. Browser tests save desktop and mobile screenshots under test-results/pit-window-desktop.png and test-results/pit-window-mobile.png. The draft PR records visual inspection and repository-selected verification; generated screenshots are review artifacts, not production assets or pixel-diff merge gates.

## Phase 3.4B prerequisites and limits

No production pit loss is approved. A future integration must first review eligible loss provenance, authentic lap-aware timing joins and a complete roster; unknown or stale values must remain unavailable. It must route through existing delayed/replay context boundaries and validate corrections, seeks, pause and reconnect. This task does not establish those runtime adapters or claim real-race accuracy.

Phase 3.4B must separately review whether any integration should be enabled, the selected-driver interaction contract, source/availability labels, official tie semantics versus ordinal slots, reference-pace/correlation limitations, localization, light-theme/HA palette validation and full-grid usability. Window-based effective loss must never appear as immediate pit-exit output. Synthetic fixtures must remain outside production configuration. No runtime integration or automatic deployment/publication is authorized by this report.
