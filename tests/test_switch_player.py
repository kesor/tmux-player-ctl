#!/usr/bin/env python3
"""Test switch_player failure state handling."""

import unittest
from unittest.mock import patch
import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestSwitchPlayerFailure(unittest.TestCase):
    """Test that switch_player handles failure gracefully."""

    def setUp(self):
        self._orig = tpc.s
        tpc.s = tpc.PlayerTracker()
        tpc.s.state = tpc.PlayerState()

    def tearDown(self):
        tpc.s = self._orig

    @patch.object(tpc, "get_available_players")
    def test_switch_to_no_players_clears_current_player(self, mock_players):
        """When switching to no players, current_player should be cleared."""
        # Setup: currently have a player
        tpc.s.current_player = "spotifyd"
        tpc.s.current_player_idx = 0
        tpc.s.state.player = "spotifyd"
        tpc.s.state.status = "Playing"
        tpc.s.available_players = ["spotifyd"]

        # Simulate no players available
        mock_players.return_value = []

        # Switch
        result = tpc.switch_player()

        # Verify: current_player should be cleared
        self.assertEqual(tpc.s.current_player, "",
            "current_player should be cleared when no players available")
        self.assertEqual(tpc.s.current_player_idx, -1,
            "current_player_idx should be -1 when no players")

    @patch.object(tpc, "get_available_players")
    def test_switch_to_no_players_sets_status_no_player(self, mock_players):
        """When switching to no players, status should indicate no player."""
        mock_players.return_value = []
        result = tpc.switch_player()

        self.assertIn("No player", tpc.s.state.status)
        self.assertIsNone(result)

    @patch.object(tpc, "get_available_players")
    def test_switch_preserves_selected_player_when_still_available(self, mock_players):
        """When current player is still available, keep it selected."""
        # Setup: had one player
        tpc.s.current_player = "spotifyd"
        tpc.s.current_player_idx = 0
        tpc.s.available_players = ["spotifyd"]

        # Now two players available
        mock_players.return_value = ["mpd", "spotifyd"]

        # Switch should go to index 1 (spotifyd is still there, go to next)
        with patch.object(tpc, "start_metadata_follower"):
            result = tpc.switch_player()

        self.assertEqual(tpc.s.current_player_idx, 1)
        self.assertEqual(tpc.s.current_player, "spotifyd")


if __name__ == "__main__":
    unittest.main(verbosity=2)
