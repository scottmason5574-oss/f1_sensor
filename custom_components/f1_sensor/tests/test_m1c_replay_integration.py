"""Synthetic chronological playback through transport, bus and analysis."""

import json

from custom_components.f1_sensor import _DelayedAnalysisBus
from custom_components.f1_sensor.analysis import Phase4AnalysisStore
from custom_components.f1_sensor.history import LapAnalysisStore
from custom_components.f1_sensor.replay_mode import ReplayIndex, ReplayTransport
from custom_components.f1_sensor.signalr import LiveBus


async def test_chronological_replay_gap(hass, tmp_path):
    """Keep field age, apply corrections, and invalidate incompatible epochs."""
    a = {"1": {"Position": 1}, "2": {"Position": 2}}
    b = {"1": {"Position": 2}, "2": {"Position": 1}}
    frames = [
        (0, "SessionInfo", {"Key": "synthetic-a", "Type": "Race"}),
        (1, "TimingData", {"Lines": a}),
        (2, "TimingData", {"Lines": {"2": {"GapToLeader": "+2.0"}}}),
        (2, "TimingData", {"Lines": {"2": {"GapToLeader": "+2.1"}}}),
        (3, "TimingData", {"Lines": {"2": {"NumberOfLaps": 2}}}),
        (4, "TimingData", {"Lines": b}),
        (5, "TimingData", {"Lines": a}),
        (6, "TimingData", {"Lines": {"2": {"GapToLeader": "+3.0"}}}),
        (7, "SessionInfo", {"Key": "synthetic-b", "Type": "Race"}),
        (8, "TimingData", {"Lines": a}),
        (9, "TimingData", {"Lines": {"2": {"GapToLeader": "+4.0"}}}),
    ]
    path = tmp_path / "synthetic.jsonl"
    path.write_text(
        "".join(json.dumps({"t": t, "s": s, "p": p}) + "\n" for t, s, p in frames),
        encoding="utf-8",
    )
    index = ReplayIndex("synthetic", len(frames), 9, 0, path, tmp_path / "index")
    transport = ReplayTransport(hass, index)
    bus = LiveBus(hass, None, transport_factory=lambda: transport)
    delayed = _DelayedAnalysisBus(hass, bus, 0, None, None)
    laps = LapAnalysisStore(delayed, source_provider=lambda: "replay")
    analysis = Phase4AnalysisStore(delayed, laps, source_provider=lambda: "replay")
    snapshots = []
    try:
        async for message in transport.messages():
            bus._process_payload(message)
            snapshots.append(analysis.snapshot()["replay_race_gap"])
        assert snapshots[2]["observations"][0]["gap"] == "+2.0"
        assert snapshots[3]["observations"][0]["gap"] == "+2.1"
        assert snapshots[4]["observations"] == snapshots[3]["observations"]
        assert snapshots[4]["as_of"] == 0.003
        assert snapshots[4]["observations"][0]["event_time"] == 0.002
        assert snapshots[5]["leader"] == 2
        assert snapshots[6]["leader"] == 1
        assert snapshots[6]["epoch"] > snapshots[4]["epoch"]
        assert snapshots[5]["observations"] == snapshots[6]["observations"] == []
        assert snapshots[7]["observations"][0]["gap"] == "+3.0"
        assert snapshots[8] is None
        assert snapshots[10]["observations"][0]["gap_seconds"] == 4.0
        bus.inject_message("TimingData", {"Lines": a})
        assert analysis.snapshot()["replay_race_gap"] is None
    finally:
        await analysis.async_close()
        await laps.async_close()
        await delayed.async_close()
        await transport.close()
