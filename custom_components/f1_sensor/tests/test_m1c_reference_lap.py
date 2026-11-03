"""Synthetic eligibility contracts and analysis/history integration."""

from dataclasses import replace

import pytest

from custom_components.f1_sensor.analysis import Phase4AnalysisStore
from custom_components.f1_sensor.history import LapAnalysisStore
from custom_components.f1_sensor.reference_lap import LapEvidence, reference_lap
from custom_components.f1_sensor.signalr import LiveBus, ReplayTimingDelta


def _verified(lap, duration):
    return LapEvidence(
        lap=lap,
        started_at=lap * 100 - 90,
        finished_at=lap * 100,
        available_at=lap * 100,
        duration=duration,
        completed=True,
        valid=True,
        leader=True,
        green=True,
        pit_affected=False,
    )


@pytest.mark.parametrize(
    ("as_of", "expected"),
    [
        (600, (84, 5, "five_samples")),
        (300, (82, 3, "provisional")),
        (100, (81, 1, "provisional")),
        (99, (None, 0, "no_available_laps")),
    ],
)
def test_recent_samples(as_of, expected):
    laps = [_verified(lap, 80 + lap) for lap in range(1, 7)]
    assert reference_lap(reversed(laps), as_of) == expected


@pytest.mark.parametrize(
    ("evidence", "reason"),
    [
        pytest.param({"valid": None}, "eligibility_unverified", id="validity-missing"),
        pytest.param({"valid": False}, "no_eligible_laps", id="invalid"),
        pytest.param(
            {"completed": None}, "eligibility_unverified", id="completion-missing"
        ),
        pytest.param({"completed": False}, "no_eligible_laps", id="unfinished"),
        pytest.param({"pit_affected": True}, "no_eligible_laps", id="pit-affected"),
        pytest.param(
            {"pit_affected": None}, "eligibility_unverified", id="pit-unknown"
        ),
        pytest.param({"green": False}, "no_eligible_laps", id="sc-vsc-or-red"),
        pytest.param(
            {"green": None}, "eligibility_unverified", id="status-coverage-gap"
        ),
        pytest.param(
            {"leader": None}, "eligibility_unverified", id="leader-unverified"
        ),
        pytest.param(
            {"leader": False}, "no_eligible_laps", id="leadership-interrupted"
        ),
        pytest.param(
            {"started_at": None}, "eligibility_unverified", id="boundary-missing"
        ),
        pytest.param(
            {"finished_at": 101}, "no_eligible_laps", id="finish-after-observation"
        ),
        pytest.param({"duration": 0}, "no_eligible_laps", id="zero-duration"),
        pytest.param(
            {"duration": float("inf")}, "no_eligible_laps", id="infinite-duration"
        ),
    ],
)
def test_ineligible_or_unknown_sample(evidence, reason):
    assert reference_lap([replace(_verified(1, 80), **evidence)], 100) == (
        None,
        0,
        reason,
    )


def test_as_of_corrections_and_duplicates():
    first = _verified(1, 80)
    corrected = replace(first, available_at=120, duration=82)
    corrected_again = replace(corrected, duration=84)
    revoked = replace(corrected_again, available_at=140, valid=False)
    laps = [first, first, corrected, corrected_again, revoked, _verified(2, 81)]

    assert reference_lap(laps, 119) == (80, 1, "provisional")
    assert reference_lap(laps, 120) == (84, 1, "provisional")
    assert reference_lap(laps, 140) == (None, 0, "no_eligible_laps")
    assert reference_lap(laps, 200) == (81, 1, "provisional")
    assert reference_lap(laps, 119) == (80, 1, "provisional")


@pytest.mark.parametrize("provider", ["f1_live", "replay"])
async def test_reference_lap_analysis_candidates(hass, provider):
    """Producer-shaped timing rows cannot certify whole-lap eligibility."""
    bus = LiveBus(hass, None)
    history = LapAnalysisStore(bus, source_provider=lambda: provider)
    analysis = Phase4AnalysisStore(bus, history, source_provider=lambda: provider)
    try:
        bus.inject_message("SessionInfo", {"Key": "synthetic-a", "Type": "Race"})
        bus.inject_message("TrackStatus", {"Status": "1", "Message": "AllClear"})
        timing = {
            "Lines": {
                "44": {
                    "Position": 1,
                    "NumberOfLaps": 5,
                    "LastLapTime": {"Value": "1:30.100"},
                    "InPit": False,
                    "PitOut": False,
                }
            }
        }
        payload = ReplayTimingDelta(timing, 500) if provider == "replay" else timing
        bus.inject_message("TimingData", payload)
        assert history.get_lap(44, 5)["lap_duration"] == pytest.approx(90.1)
        snapshot = analysis.snapshot()["reference_lap"]
        assert snapshot["duration_seconds"] is None
        assert snapshot["sample_count"] == 0
        if provider == "f1_live":
            assert snapshot["reason"] == "eligibility_unverified"
            assert snapshot["candidates"] == [
                {
                    "driver_number": 44,
                    "lap_number": 5,
                    "reported_duration_seconds": pytest.approx(90.1),
                    "eligibility": "unknown",
                }
            ]
        else:
            assert snapshot["reason"] == "replay_lap_provenance_unavailable"
            assert snapshot["candidates"] == []

        bus.inject_message("SessionInfo", {"Key": "synthetic-b", "Type": "Race"})
        assert history.get_lap(44, 5) is None
        assert analysis.snapshot()["reference_lap"]["candidates"] == []
        history.reset_for_replay()
        analysis.reset_for_replay()
        assert (
            analysis.snapshot()["reference_lap"]["reason"] == "race_session_unavailable"
        )
    finally:
        await analysis.async_close()
        await history.async_close()


async def test_reference_lap_stays_unavailable_across_controller_seeks(hass, tmp_path):
    """A future synthetic replay completion cannot become a reference candidate."""
    from custom_components.f1_sensor import _build_replay_reset_callbacks
    from custom_components.f1_sensor.const import DOMAIN
    from custom_components.f1_sensor.tests.test_replay_seek import (
        ENTRY_ID,
        _setup_controller,
    )

    session = {"Key": "synthetic-seek", "Type": "Race"}
    frames = [
        (0, "SessionInfo", session),
        (
            100,
            "TimingData",
            {"Lines": {"44": {"NumberOfLaps": 1, "LastLapTime": {"Value": "1:30"}}}},
        ),
        (
            200,
            "TimingData",
            {"Lines": {"44": {"NumberOfLaps": 2, "LastLapTime": {"Value": "1:29"}}}},
        ),
    ]
    controller, _, bus, _ = await _setup_controller(
        hass,
        tmp_path,
        initial_state={"SessionInfo": session},
        frames=frames,
        coordinators=(),
    )
    history = LapAnalysisStore(bus, source_provider=lambda: "replay")
    analysis = Phase4AnalysisStore(bus, history, source_provider=lambda: "replay")
    hass.data[DOMAIN][ENTRY_ID]["replay_reset_callbacks"] = (
        _build_replay_reset_callbacks(history, analysis)
    )
    expected = {
        "duration_seconds": None,
        "sample_count": 0,
        "reason": "replay_lap_provenance_unavailable",
        "candidates": [],
    }
    try:
        await controller.async_seek_to_ms(100)
        await controller.async_play()
        assert history.get_lap(44, 1) is not None
        assert history.get_lap(44, 2) is None
        assert analysis.snapshot()["reference_lap"] == expected

        await controller.async_seek_to_ms(200)
        assert history.get_lap(44, 2) is not None
        assert analysis.snapshot()["reference_lap"] == expected

        await controller.async_seek_to_ms(100)
        assert history.get_lap(44, 2) is None
        assert analysis.snapshot()["reference_lap"] == expected
    finally:
        await controller.async_stop()
        await analysis.async_close()
        await history.async_close()
