---
id: circle-of-doom-source-of-truth
title: Circle of Doom source of truth
description: Circle of Doom source of truth for F1 Sensor.
---

# Circle of Doom source of truth

The goal is a native Home Assistant Track Map mode for desktop and mobile. Preserve the physical view as the default. Add a time-based circle with team colors, selection, smooth markers, lap and race status, lap-deficit handling and eventually an inner pit lane. Pair it with a selected-driver straight pit window showing loss range, projected rejoin, gap labels and nearby traffic. Both views consume one prediction result and follow live, Live Delay and replay without a MultiViewer runtime.

## Reference evidence

| Project | Evidence and intended use | Limits |
| --- | --- | --- |
| MultiViewer Circle of Doom | Prior static inspection of v2.13.1 found a median-based reference lap and conversion of time gap divided by reference duration to turns. The race reference uses consecutive leader final-segment crossings, coverage checks, an all-clear filter when status exists, screening around the candidate median, and a median of up to five retained laps. Prior reports also describe animated circular markers, driver highlighting, an inner pit path, pit overlays and virtual markers. [MultiViewer](https://multiviewer.app/) | Static findings carry no runtime guarantee. Exact anchoring, lapped behavior, purple/orange regions, virtual rejoin calculation, pit animation and special race conditions remain open. |
| Pit Wall by JD | GHOST RING documentation describes the median of completed green-stop losses, calculated from in-lap plus out-lap less twice normal pace, with a per-circuit fallback. It gives approximate SC and VSC multipliers of 0.52 and 0.62 and uses recent green leader laps for lap length. Rejoin and traffic visualization inform our UX. [GHOST RING documentation](https://pitwall.jdvb.com.au/about) | These are published descriptions. Sample filters, pace estimation and predictive accuracy were not independently established. F1 Sensor would calibrate its own model and treat red flags separately. |
| PITWALL.info | The site documents a timing-estimated circle and a pit window. Use the compact layout and selected-driver linear traffic presentation as design references, including on narrow screens. [PITWALL.info](https://www.pitwall.info/) | Exact estimation and pit-window calculations remain unverified. The relationship to WarmBed/PITWALL is unestablished. This is a separate project from JD's. |
| F1 StratLab | Earlier research identifies TrackRing.tsx under src/pitwall/ui/src/features/data as an SVG design reference for team-colored markers, labels, statuses and missing positions. Its reported input is lap-distance fraction, which represents a different quantity from time gap. [F1 StratLab](https://github.com/VforVitorio/F1-StratLab) | Exact file revision and behavior remain unverified. Check file provenance and applicable Apache-2.0 obligations before any reuse. |

Use an independent implementation. The private handoff, static REA reports, API inventory and combined report remain with the original research bundle. Local topic schemas and seek behavior were not runtime-confirmed. This public summary contains findings only.

## Product boundaries

Current-race observed losses, documented historical or circuit fallbacks, uncertainty and projected virtual markers are intended features. A stale or unrankable driver should retain an explicit status. Red flags, SC/VSC transitions, lap wrapping, missing timing and delayed/replayed updates require explicit behavior. Purple/orange parity is optional and requires separate evidence. See the [repository audit](./CIRCLE_OF_DOOM_REPOSITORY_AUDIT.md) and [implementation plan](./CIRCLE_OF_DOOM_IMPLEMENTATION_PLAN.md).
