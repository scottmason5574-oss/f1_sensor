# Circle of Doom M1D Task 2 historical cross-check

**PARTIAL.** OpenF1 confirms numeric gap behavior in a bounded race sample. The sample contains no explicit lap deficit or change of leader, and its retrospective records do not satisfy the M1C reference-lap contract.

## Source and scope

OpenF1 is a third-party processed source. Its public documentation permits unauthenticated historical queries from 2023 and separates live access into a paid tier. The documentation reviewed did not specify separate historical retention terms. This research used bounded unauthenticated requests and retained only selected observations and query links in this report. [OpenF1 documentation](https://openf1.org/docs/)

The session lookup returned HTTP 200 for race **9165**, meeting **1219**, at Marina Bay, Singapore, on **2023-09-17**, with listed start and end at **12:00 and 14:00 UTC**. The core timing window is 13:29–13:33 UTC. Short supplemental queries cover the preceding race-control and pit sequence and a 15-second late-race token check. [Session metadata](https://api.openf1.org/v1/sessions?session_key=9165)

| Source | Query scope and access |
| --- | --- |
| Intervals | [13:30:25–13:31:25](https://api.openf1.org/v1/intervals?session_key=9165&date%3E2023-09-17T13:30:25&date%3C2023-09-17T13:31:25), HTTP 200, 236 rows. [13:45:00–13:45:15](https://api.openf1.org/v1/intervals?session_key=9165&date%3E2023-09-17T13:45:00&date%3C2023-09-17T13:45:15), HTTP 200, 59 rows. |
| Position | [13:29–13:33](https://api.openf1.org/v1/position?session_key=9165&date%3E2023-09-17T13:29&date%3C2023-09-17T13:33) and [driver 55 before 13:33](https://api.openf1.org/v1/position?session_key=9165&driver_number=55&date%3C2023-09-17T13:33), both HTTP 200. |
| Laps | Approximate starts in 13:29–13:33 for [driver 55](https://api.openf1.org/v1/laps?session_key=9165&driver_number=55&date_start%3E2023-09-17T13:29&date_start%3C2023-09-17T13:33) and [driver 1](https://api.openf1.org/v1/laps?session_key=9165&driver_number=1&date_start%3E2023-09-17T13:29&date_start%3C2023-09-17T13:33), both HTTP 200. |
| Pit | [13:18–13:25](https://api.openf1.org/v1/pit?session_key=9165&date%3E2023-09-17T13:18&date%3C2023-09-17T13:25), HTTP 200, six rows. Both 13:25–13:29 and [13:29–13:33](https://api.openf1.org/v1/pit?session_key=9165&date%3E2023-09-17T13:29&date%3C2023-09-17T13:33) returned HTTP 404 with “No results found.” |
| Race control | [13:18–13:25](https://api.openf1.org/v1/race_control?session_key=9165&date%3E2023-09-17T13:18&date%3C2023-09-17T13:25), 13:25–13:29, and [13:29–13:33](https://api.openf1.org/v1/race_control?session_key=9165&date%3E2023-09-17T13:29&date%3C2023-09-17T13:33), all HTTP 200. |
| Stints | [Driver 55](https://api.openf1.org/v1/stints?session_key=9165&driver_number=55), HTTP 200, two lap-indexed rows. |

## Time-aligned historical observations

All times below are UTC on 2023-09-17. Gap and interval values are in seconds.

| Time | Driver | Observation |
| --- | --- | --- |
| 13:18:06 | Session | Race control reports VSC deployed. |
| 13:20:52.511 | 63 | Pit record assigned to lap 44, during the reported VSC period. |
| 13:21:29 / 13:21:44 | Session | Race control reports VSC ending, then track clear. Later sector 13 yellow at 13:24:47 and clear at 13:25:03 show why a single clear message cannot certify a whole lap. |
| 13:30:30.583 | 1 | Gap 40.502, interval 0.491. |
| 13:30:34.880 | 55 | Gap 0.0, interval 0.0. Driver 55's position query returned only position 1 at 11:01:04.137. |
| 13:30:35.005 | 55 | Approximate start of lap 51. |
| 13:30:36.083 | 1 | Gap 40.588, interval 0.404. |
| 13:31:02.395 | 1 | Gap 41.019, interval 0.003. |
| 13:31:08.848 | 1 and 40 | Position records report 1 in eighth and 40 in ninth. At that timestamp driver 1's gap is 40.857 and interval is 6.159. |
| 13:31:15.598 | 1 | Approximate start of lap 51. |
| 13:32:13.050 | 55 | Approximate start of lap 52. The reported duration of lap 51 is 98.040 seconds. |

Driver 1's gap stayed close to 40 seconds on both sides of the reported driver 55 boundary. Between their reported starts of lap 51, the lap rows imply a one-lap difference in completed counts despite a numeric time gap. This is an inference from approximate lap starts. The data does not expose raw completed-lap counters or exact crossing order at subsecond resolution. The eighth/ninth position update coincides with a sharp change in interval while the gap to the leader stays close to 41 seconds. It does not exercise a new leader anchor.

The main interval slice had two explicit null gaps and every row carried the gap field. Neither interval slice returned a string gap. The OpenF1 schema documents the spelling `+1 LAP` and describes a null leader gap, while the apparent leader's observed value was numeric zero. Treat this as variation relative to the OpenF1 description. A null alone cannot establish the reason for unavailability. The sample does not verify token onset or removal.

In the 60-second slice driver 1 had 16 interval rows and driver 55 had one. The four-minute position query produced two rows at one timestamp. Lap rows follow lap boundaries, while race control and pit report individual events. The common UTC basis supports retrospective as-of joins with explicit tolerances and age limits. Row counts measure returned updates. They cannot establish publication latency, missing packets, producer correction precedence or original SignalR field omission.

## Reference-lap evidence

Candidate for assessment is driver 55's lap 51. The classifications apply to the historical candidate, with verified duration meaning that OpenF1 reports a completed duration.

| Requirement | Classification | Evidence and limit |
| --- | --- | --- |
| Completed duration | Verified | Lap 51 reports 98.040 s. |
| Start and finish boundaries | Partial | Approximate start 13:30:35.005. Start plus duration gives 13:32:13.045, five milliseconds before the reported next start. Agreement does not independently verify both crossings. |
| Leadership throughout | Partial | Latest recorded position for 55 is first and the interval slice includes a zero gap. The sparse classification excerpt does not certify continuous coverage. |
| Green throughout | Partial | Race control reports earlier VSC and sector transitions. No affirmative whole-lap coverage is established for lap 51. |
| Pit entry and exit exclusion | Partial | Lap 51 reports `is_pit_out_lap=false` and stint 2 covers laps 21–62 on hard tyres. The empty pit window cannot prove both boundary exclusions. |
| Validity and revisions | Missing | The sampled lap row has no positive validity or revision field. |
| Observation availability | Unknown | Historical rows expose event or approximate start times. The first availability time and later revisions are unknown. |

## M1C compatibility and next dependency

**Insufficient evidence for the full contract.** The observed distinct positive gap and interval support keeping the two fields separate. The lap boundary comparison supports withholding inferred whole-lap deficits from lap count alone. The processed source's leader zero is compatible with M1C deriving relative zero from classification. No concrete application defect was established.

The Task 1 findings still govern source-specific behavior. Neither epoch timing at a lead change nor correction precedence, raw field omission or counted-token grammar was validated here. The reference selector in `custom_components/f1_sensor/reference_lap.py` requires verified boundaries, continuous green and leadership, validity, pit exclusion and a revision availability clock. This sample supplies a completed duration and useful context but no certified reference. M2 remains gated.

For Task 3, obtain a producer-authorized timestamped excerpt with explicit lapping and leadership changes, and companion lap validity, crossing, status and pit events with availability or sequence metadata. Use it to test one complete green leader lap and one excluded or revised lap against the same as-of clock, then compare live ingestion with chronological and cold-seek replay.
