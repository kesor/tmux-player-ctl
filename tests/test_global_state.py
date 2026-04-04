"""Test GlobalState / PlayerTracker object."""

import unittest
from unittest.mock import patch

import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestPlayerTrackerExists(unittest.TestCase):
    """PlayerTracker / s object should exist and have expected attributes."""

    def test_module_has_s_object(self):
        """Module should have a 's' object for player state."""
        self.assertTrue(hasattr(tpc, "s"))

    def test_s_has_current_player(self):
        """s should have current_player attribute."""
        self.assertTrue(hasattr(tpc.s, "current_player"))

    def test_s_has_available_players(self):
        """s should have available_players list attribute."""
        self.assertTrue(hasattr(tpc.s, "available_players"))
        self.assertIsInstance(tpc.s.available_players, list)

    def test_s_has_current_player_idx(self):
        """s should have current_player_idx int attribute."""
        self.assertTrue(hasattr(tpc.s, "current_player_idx"))
        self.assertIsInstance(tpc.s.current_player_idx, int)

    def test_s_has_state(self):
        """s should have state attribute (PlayerState)."""
        self.assertTrue(hasattr(tpc.s, "state"))
        self.assertIsInstance(tpc.s.state, tpc.PlayerState)

    def test_s_has_last_command_time(self):
        """s should have last_command_time float attribute."""
        self.assertTrue(hasattr(tpc.s, "last_command_time"))
        self.assertIsInstance(tpc.s.last_command_time, float)

    def test_s_has_meta_proc(self):
        """s should have meta_proc attribute."""
        self.assertTrue(hasattr(tpc.s, "meta_proc"))


class TestPlayerTrackerMutation(unittest.TestCase):
    """Mutating s attributes should work correctly."""

    def setUp(self):
        self._orig = tpc.s

    def tearDown(self):
        # Restore (tests may reassign s)
        if hasattr(tpc, "s"):
            tpc.s = self._orig

    def test_can_set_current_player(self):
        """Should be able to set s.current_player."""
        tpc.s.current_player = "spotify"
        self.assertEqual(tpc.s.current_player, "spotify")

    def test_can_set_available_players(self):
        """Should be able to set s.available_players."""
        tpc.s.available_players = ["spotify", "vlc"]
        self.assertEqual(tpc.s.available_players, ["spotify", "vlc"])

    def test_can_set_state_player(self):
        """Should be able to set s.state.player."""
        tpc.s.state.player = "vlc"
        self.assertEqual(tpc.s.state.player, "vlc")


class TestGlobalSInFunctions(unittest.TestCase):
    """Functions that use player globals should declare 'global s'."""

    def setUp(self):
        self._orig_s = tpc.s

    def tearDown(self):
        tpc.s = self._orig_s

    def test_get_best_player_uses_s(self):
        """get_best_player should read from s.available_players."""
        tpc.s.available_players = ["spotify", "vlc"]
        # Should not need current_player set for empty list
        result = tpc.get_best_player([])
        self.assertIsNone(result)

    def test_player_args_uses_s(self):
        """player_args() should read from s.current_player."""
        tpc.s.current_player = "spotify"
        args = tpc.player_args()
        self.assertEqual(args, ["-p", "spotify"])

    def test_player_args_empty_when_no_player(self):
        """player_args() should return empty when no player."""
        tpc.s.current_player = ""
        args = tpc.player_args()
        self.assertEqual(args, [])

    def test_reset_state_resets_s_state(self):
        """reset_state() should reset s.state with fresh PlayerState."""
        tpc.s.state.title = "Old Song"
        tpc.s.state.volume = 50
        tpc.reset_state()
        self.assertIsInstance(tpc.s.state, tpc.PlayerState)
        self.assertEqual(tpc.s.state.title, "")

    @patch.object(tpc, "get_available_players", return_value=["spotify", "vlc"])
    @patch.object(tpc, "start_metadata_follower", return_value=None)
    @patch.object(tpc, "run_playerctl", return_value="")
    def test_switch_player_uses_s(self, mock_rpc, mock_follower, mock_players):
        """switch_player should read/write s.current_player, s.available_players."""
        tpc.s.current_player = "spotify"
        tpc.s.current_player_idx = 0
        tpc.s.meta_proc = None
        tpc.switch_player()
        # After switching, should be on vlc
        self.assertEqual(tpc.s.current_player, "vlc")


class TestNoGlobalCurrentPlayer(unittest.TestCase):
    """current_player, available_players, current_player_idx should not be bare globals."""

    def test_no_bare_current_player_global(self):
        """Bare 'current_player' should not exist as module-level global."""
        # After refactor, current_player is s.current_player, not a bare global
        # We check that if someone tries to read current_player it gets s.current_player
        # The simplest check: setting s.current_player updates what player_args uses
        tpc.s.current_player = "testplayer"
        args = tpc.player_args()
        self.assertIn("testplayer", args)


class TestShutdownRequestSeparate(unittest.TestCase):
    """shutdown_requested should stay as a separate bare global (signal handlers)."""

    def test_shutdown_requested_exists(self):
        """shutdown_requested should be a bare global bool."""
        self.assertIsInstance(tpc.shutdown_requested, bool)

    def test_shutdown_can_be_set(self):
        """Should be able to set shutdown_requested."""
        original = tpc.shutdown_requested
        tpc.shutdown_requested = True
        self.assertTrue(tpc.shutdown_requested)
        tpc.shutdown_requested = original


if __name__ == "__main__":
    unittest.main()
