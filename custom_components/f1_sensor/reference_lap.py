"""Select a reference from independently verified completed leader laps."""

from collections.abc import Iterable
from dataclasses import dataclass
from heapq import nlargest
from math import isfinite


@dataclass(frozen=True, slots=True)
class LapEvidence:
    """One revision of a race lap in a single session and clock domain.

    Lap is the race lap number, shared across revisions even if the leader
    identity is corrected. The producer must verify boundaries and eligibility
    against the whole lap. In particular, green and leader each attest to
    continuous coverage, and None represents missing evidence.
    """

    lap: int
    started_at: float | None
    finished_at: float | None
    available_at: float
    duration: float | None
    completed: bool | None = None
    valid: bool | None = None
    leader: bool | None = None
    green: bool | None = None
    pit_affected: bool | None = None

    @property
    def eligible(self) -> bool | None:
        """Report certified eligibility, known exclusion, or missing evidence."""
        required = (self.completed, self.valid, self.leader, self.green)
        if any(flag is False for flag in required) or self.pit_affected is True:
            return False
        if self.duration is not None and (
            not isfinite(self.duration) or self.duration <= 0
        ):
            return False
        if (
            self.started_at is None
            or self.finished_at is None
            or self.duration is None
            or not all(flag is True for flag in required)
            or self.pit_affected is not False
        ):
            return None
        return (
            isfinite(self.available_at)
            and isfinite(self.started_at)
            and isfinite(self.finished_at)
            and self.started_at < self.finished_at <= self.available_at
        )


def reference_lap(
    observations: Iterable[LapEvidence], as_of: float
) -> tuple[float | None, int, str]:
    """Select the median of the newest five qualifying race laps.

    Input is one session's retained revisions, in producer order for ties.
    The selector retains no history across calls. Availability is evaluated
    before eligibility so that a known revocation can replace an older sample.
    """
    if not isfinite(as_of):
        return None, 0, "invalid_as_of"

    latest: dict[int, LapEvidence] = {}
    for item in observations:
        if (
            item.lap <= 0
            or not isfinite(item.available_at)
            or item.available_at > as_of
        ):
            continue
        previous = latest.get(item.lap)
        if previous is None or item.available_at >= previous.available_at:
            latest[item.lap] = item
    if not latest:
        return None, 0, "no_available_laps"

    eligible = nlargest(
        5,
        (item for item in latest.values() if item.eligible is True),
        key=lambda item: (item.finished_at, item.lap),
    )
    if not eligible:
        reason = (
            "eligibility_unverified"
            if any(item.eligible is None for item in latest.values())
            else "no_eligible_laps"
        )
        return None, 0, reason

    durations = sorted(item.duration for item in eligible if item.duration is not None)
    count = len(durations)
    midpoint = count // 2
    upper = durations[midpoint]
    lower = durations[(count - 1) // 2]
    return (
        lower + (upper - lower) / 2,
        count,
        ("provisional" if count < 5 else "five_samples"),
    )
