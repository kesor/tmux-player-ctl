#!/usr/bin/env python3
"""
Integration tests that run actual playerctl commands.
These tests require playerctl to be installed and may require a media player running.
Run with: python3 -m unittest integration
"""

import unittest

import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestPlayerctlIntegration(unittest.TestCase):
    """Integration tests that run actual playerctl commands."""

    def test_list_players(self):
        """Should list available players without error."""
        players = tpc.get_available_players()
        # Just verify it returns a list (may be empty if no players)
        self.assertIsInstance(players, list)

    def test_get_status(self):
        """Should get status without error if a player is available."""
        players = tpc.get_available_players()
        if not players:
            self.skipTest("No media players available")

        status = tpc.run_playerctl("status")
        self.assertIn(status, ["Playing", "Paused", "Stopped", ""])

    def test_get_metadata_format(self):
        """Should get metadata in expected format."""
        players = tpc.get_available_players()
        if not players:
            self.skipTest("No media players available")

        result = tpc.run_playerctl("--format", "{{status}}", "status")
        self.assertIn(result, ["Playing", "Paused", "Stopped"])


if __name__ == "__main__":
    unittest.main()
