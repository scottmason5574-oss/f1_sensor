"""Synthetic archive-offset regression cases."""

import unittest

from custom_components.f1_sensor.replay_gap import ReplayGapState


class ReplayGapTest(unittest.TestCase):
    def test_sparse_correction_and_epoch(self):
        state = ReplayGapState()
        state.apply(0, {"1": {"Position": 1}, "2": {"Position": 2}})
        state.apply(1, {"2": {"GapToLeader": "+2.0"}})
        state.apply(1, {"2": {"GapToLeader": "+2.1"}})
        state.apply(2, {"2": {"NumberOfLaps": 2}})
        self.assertEqual(state.gap("2", 2, 1), "+2.1")
        self.assertIsNone(state.gap("2", 2, 0))
        self.assertIsNone(state.gap("2", 1, 10))
        state.apply(3, {"1": {"Position": 2}, "2": {"Position": 1}})
        state.apply(4, {"1": {"Position": 1}, "2": {"Position": 2}})
        self.assertIsNone(state.gap("2", 4, 10))
        state.apply(5, {"2": {"GapToLeader": "+3.0"}})
        self.assertEqual(state.gap("2", 5, 0), "+3.0")
        state.apply(None, {"2": {"GapToLeader": "+4.0"}})
        self.assertIsNone(state.gap("2", 5, 10))


if __name__ == "__main__":
    unittest.main()
