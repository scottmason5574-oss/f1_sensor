"""Exercise estimated phase through the existing analysis bus and snapshot."""

from types import SimpleNamespace

import pytest

from custom_components import f1_sensor as f1
from custom_components.f1_sensor.analysis import Phase4AnalysisStore
from custom_components.f1_sensor.history import LapAnalysisStore
from custom_components.f1_sensor.signalr import (
    LiveTimingDelta,
    ReplayTimingCheckpoint,
    ReplayTimingDelta,
)
from custom_components.f1_sensor.tests.test_phase_4_analysis import _Bus


def _start_race(bus, key=41):
    bus.emit("SessionInfo", {"Key": key, "Type": "Race", "Name": "Race"})
    bus.emit("SessionStatus", {"Status": "Started"})
    bus.emit("TrackStatus", {"Status": "1"})


@pytest.mark.parametrize("delay", [0, 30])
async def test_circle_anchor_uses_released_driver_transition(hass, monkeypatch, delay):
    clock = SimpleNamespace(value=100.0)
    monkeypatch.setattr(f1, "time", SimpleNamespace(monotonic=lambda: clock.value))
    raw = _Bus()
    delayed = f1._DelayedAnalysisBus(hass, raw, delay, None, None)

    def provider():
        return "f1_live"

    laps = LapAnalysisStore(delayed, source_provider=provider)
    analysis = Phase4AnalysisStore(delayed, laps, source_provider=provider)

    def timing(stamp, leader, **follower):
        raw.emit(
            "TimingData",
            LiveTimingDelta({"Lines": {"4": leader, "1": follower}}, stamp),
        )

    try:
        _start_race(raw)
        timing(100, {"Position": "1", "NumberOfLaps": 8}, Position="2")
        timing(102, {"NumberOfLaps": 9, "LastLapTime": {"Value": "1:29.000"}})
        timing(104, {}, GapToLeader="+9.0", NumberOfLaps=8)
        timing(106, {"NumberOfLaps": 10, "LastLapTime": {"Value": "1:31.000"}})
        if delay:
            assert analysis.snapshot()["estimated_circle"] is None
            clock.value += delay
            f1._drain_delayed_ingest_queue(delayed)

        snapshot = analysis.snapshot()
        phase = snapshot["estimated_circle"]
        assert phase["session_key"] == "41"
        assert phase["anchor"] == phase["as_of"] == 106
        assert phase["duration_seconds"] == 90
        assert snapshot["reference_lap"]["duration_seconds"] is None
        assert snapshot["timing"][1]["gap_observation"]["event_time"] == 104
        assert len(raw.callbacks["TimingData"]) == 1

        timing(107, {"Position": "2"}, Position="1")
        if delay:
            clock.value += delay
            f1._drain_delayed_ingest_queue(delayed)
        assert analysis.snapshot()["estimated_circle"]["anchor"] is None
        analysis.reset_for_replay()
        assert analysis.snapshot()["estimated_circle"] is None
    finally:
        await analysis.async_close()
        await laps.async_close()
        await delayed.async_close()


async def test_replay_needs_new_ordered_transition_after_checkpoint():
    bus = _Bus()
    bus.timing_generation = 0

    def provider():
        return "replay"

    laps = LapAnalysisStore(bus, source_provider=provider)
    analysis = Phase4AnalysisStore(bus, laps, source_provider=provider)

    def timing(offset, lap, **fields):
        bus.emit(
            "TimingData",
            ReplayTimingDelta(
                {"Lines": {"4": {"NumberOfLaps": lap, **fields}}}, offset
            ),
        )

    try:
        _start_race(bus)
        timing(100, 8, Position="1")
        assert analysis.snapshot()["estimated_circle"]["anchor"] is None
        timing(101, 9, LastLapTime={"Value": "1:30.000"})
        assert analysis.snapshot()["estimated_circle"]["anchor"] == 101
        bus.emit(
            "TimingData",
            ReplayTimingCheckpoint({"Lines": {}}, analysis._replay_gaps.checkpoint()),
        )
        assert analysis.snapshot()["estimated_circle"] is None
        timing(102, 10, LastLapTime={"Value": "1:31.000"})
        assert analysis.snapshot()["estimated_circle"]["anchor"] is None
        timing(103, 11, LastLapTime={"Value": "1:32.000"})
        assert analysis.snapshot()["estimated_circle"]["anchor"] == 103
        bus.timing_generation += 1
        assert analysis.snapshot()["estimated_circle"] is None
        timing(104, 10, Position="1")
        timing(105, 9)
        assert analysis.snapshot()["estimated_circle"] is None
        timing(106, 10)
        timing(107, 11, LastLapTime={"Value": "1:32.000"})
        assert analysis.snapshot()["estimated_circle"]["duration_seconds"] == 92
        for lap in range(12, 17):
            timing(107 + lap - 11, lap)
        assert analysis.snapshot()["estimated_circle"]["duration_seconds"] is None
        bus.emit("TrackStatus", {"Status": "4"})
        assert analysis.snapshot()["estimated_circle"] is None
    finally:
        await analysis.async_close()
        await laps.async_close()


async def test_retrograde_circle_frames_cannot_reseed_crossing():
    bus = _Bus()
    bus.timing_generation = 0

    def provider():
        return "f1_live"

    laps = LapAnalysisStore(bus, source_provider=provider)
    analysis = Phase4AnalysisStore(bus, laps, source_provider=provider)

    def timing(stamp, **row):
        bus.emit("TimingData", LiveTimingDelta({"Lines": {"4": row}}, stamp))
        return analysis.snapshot()["estimated_circle"] or {}

    try:
        _start_race(bus)
        timing(100, Position="1", NumberOfLaps=8)
        phase = timing(110, NumberOfLaps=9, LastLapTime={"Value": "90"})
        assert (phase["anchor"], phase["duration_seconds"]) == (110, 90)
        for stamp, row in (
            (105, {"NumberOfLaps": 8}),
            (106, {"NumberOfLaps": 8}),
            (107, {"NumberOfLaps": 9, "LastLapTime": {"Value": "91"}}),
            (111, {}),
        ):
            phase = timing(stamp, **row)
            assert phase.get("anchor") is None
            assert phase.get("duration_seconds") is None
            assert analysis._circle_watermark == max(110, stamp)

        timing(112, NumberOfLaps=9)
        assert timing(112, NumberOfLaps=10, LastLapTime={"Value": "91"}) == {}
        assert timing(113, NumberOfLaps=10).get("anchor") is None
        phase = timing(114, NumberOfLaps=11, LastLapTime={"Value": "92"})
        assert (phase["anchor"], phase["duration_seconds"]) == (114, 92)

        bus.timing_generation += 1
        timing(10, Position="1", NumberOfLaps=1)
        assert timing(11, NumberOfLaps=2, LastLapTime={"Value": "93"})["anchor"] == 11
        _start_race(bus, key=42)
        timing(1, Position="1", NumberOfLaps=1)
        phase = timing(2, NumberOfLaps=2, LastLapTime={"Value": "94"})
        assert (phase["session_key"], phase["anchor"]) == ("42", 2)
    finally:
        await analysis.async_close()
        await laps.async_close()
