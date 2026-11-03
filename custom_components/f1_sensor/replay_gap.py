"""Bounded gap provenance for ordered replay TimingData frames."""

from collections.abc import Mapping
from copy import deepcopy
from math import isfinite
import re


def replay_session_identity(payload):
    """Identify sessions consistently during archive scan and analysis delivery."""
    meeting = payload.get("Meeting")
    if not isinstance(meeting, Mapping):
        meeting = {}
    parts = (
        meeting.get("Key") or meeting.get("Id"),
        payload.get("Key") or payload.get("SessionKey") or payload.get("Path"),
        payload.get("Name"),
    )
    text = (str(part).strip() for part in parts if part is not None)
    return ":".join(filter(None, text))


class ReplayGapState:
    """Reduce archive offsets in seconds, retaining one observation per driver."""

    def __init__(self):
        self.positions = {}
        self.observations = {}
        self.leader = None
        self.epoch = 0
        self.started = None
        self.as_of = None

    def checkpoint(self):
        """Serialize the reducer state independently of merged timing fields."""
        return deepcopy(vars(self))

    @classmethod
    def restore(cls, checkpoint):
        """Restore an independent copy of index-owned state."""
        state = cls()
        for key in vars(state):
            setattr(state, key, deepcopy(checkpoint[key]))
        return state

    def apply_payload(self, offset, payload):
        """Apply the archive's sparse driver rows."""
        lines = payload.get("Lines")
        if isinstance(lines, Mapping):
            entries = lines.items()
        elif isinstance(lines, list):
            entries = enumerate(lines)
        else:
            entries = ()
        self.apply(
            offset, {str(key): row for key, row in entries if isinstance(row, Mapping)}
        )

    def apply(self, offset, lines):
        """Apply one sparse frame in archive order."""
        lines = {
            driver: row
            for driver, row in lines.items()
            if re.fullmatch(r"[1-9][0-9]{0,2}", driver)
        }
        if offset is None or not isfinite(offset):
            epoch = self.epoch
            self.__init__()
            self.epoch = epoch + 1
            return
        if self.as_of is not None and offset < self.as_of:
            if any("Position" in row for row in lines.values()):
                self.positions.clear()
                self.observations.clear()
                self.leader = None
                self.started = None
                self.epoch += 1
            return
        self.as_of = offset
        for driver, row in lines.items():
            if "Position" in row:
                self.positions[driver] = row["Position"]
        leaders = [
            driver
            for driver, position in self.positions.items()
            if str(position) == "1"
        ]
        leader = leaders[0] if len(leaders) == 1 else None
        if leader != self.leader:
            self.epoch += 1
            self.observations.clear()
            self.leader = leader
            self.started = offset if leader is not None else None
        if self.started is None or offset <= self.started:
            return
        for driver, row in lines.items():
            if driver != leader and "GapToLeader" in row:
                self.observations[driver] = (offset, row["GapToLeader"])

    def gap(self, driver, as_of, max_age):
        """Return a raw gap only within the current epoch and freshness window."""
        if self.as_of is None or as_of < self.as_of:
            return None
        observation = self.observations.get(driver)
        if observation is None:
            return None
        offset, value = observation
        return value if as_of - offset <= max_age else None
