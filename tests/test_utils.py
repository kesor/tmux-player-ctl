#!/usr/bin/env python3
"""
Test suite for utility functions.
"""

import unittest
from unittest.mock import patch, MagicMock

import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestStatusColor(unittest.TestCase):
    """Test status_color() returns correct colors."""

    def test_playing_returns_green(self):
        """Playing status should return green color."""
        result = tpc.status_color("Playing")
        self.assertEqual(result, tpc.Theme.PLAYING)

    def test_paused_returns_yellow(self):
        """Paused status should return yellow color."""
        result = tpc.status_color("Paused")
        self.assertEqual(result, tpc.Theme.PAUSED)

    def test_stopped_returns_overlay0(self):
        """Stopped status should return dim color."""
        result = tpc.status_color("Stopped")
        self.assertEqual(result, tpc.Theme.STOPPED)

    def test_recording_returns_red(self):
        """Recording status should return red color."""
        result = tpc.status_color("Recording")
        self.assertEqual(result, tpc.Theme.RECORDING)

    def test_unknown_returns_stopped(self):
        """Unknown status should return stopped color."""
        result = tpc.status_color("Unknown")
        self.assertEqual(result, tpc.Theme.STOPPED)


class TestFormatPlayerName(unittest.TestCase):
    """Test _format_player_name() - formats player name for display."""

    def test_simple_name(self):
        """Simple name is preserved."""
        result = tpc._format_player_name("spotify")
        self.assertEqual(result, "spotify")

    def test_with_instance(self):
        """Name with instance is shortened."""
        result = tpc._format_player_name("spotify.instance123")
        self.assertEqual(result, "spotify")

    def test_empty_name(self):
        """Empty name returns empty string."""
        result = tpc._format_player_name("")
        self.assertEqual(result, "")


class TestPlayerArgs(unittest.TestCase):
    """Test player_args() - returns playerctl arguments."""

    def setUp(self):
        self._orig = tpc.current_player
        tpc.current_player = ""

    def tearDown(self):
        tpc.current_player = self._orig

    def test_no_player_returns_empty(self):
        """No player returns empty list."""
        tpc.current_player = ""
        result = tpc.player_args()
        self.assertEqual(result, [])

    def test_with_player_returns_p_flag(self):
        """With player returns -p flag."""
        tpc.current_player = "spotify"
        result = tpc.player_args()
        self.assertEqual(result, ["-p", "spotify"])


class TestClearScreen(unittest.TestCase):
    """Test clear_screen() - clears terminal."""

    def test_clears_with_ansi_escape(self):
        """Should write ANSI clear sequence."""
        import io
        import sys

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        tpc.clear_screen()
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        self.assertIn("\033[2J", output)  # Clear screen
        self.assertIn("\033[H", output)  # Home cursor


class TestMoveCursor(unittest.TestCase):
    """Test move_cursor() - positions cursor."""

    def test_moves_to_position(self):
        """Should write ANSI positioning sequence."""
        import io
        import sys

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        tpc.move_cursor(5, 10)
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        self.assertEqual(output, "\033[5;10H")


class TestThemeBG(unittest.TestCase):
    """Test Theme.BG - background color from environment."""

    def test_theme_has_bg(self):
        """Theme should have BG attribute."""
        self.assertTrue(hasattr(tpc.Theme, "BG"))

    def test_theme_bg_default_empty(self):
        """Theme.BG default is empty string."""
        self.assertEqual(tpc.Theme.BG, "")


class TestPlayerctlSubprocess(unittest.TestCase):
    """Test _playerctl_subprocess - single subprocess spawner."""

    @patch.object(tpc, "_playerctl_subprocess")
    def test_returns_completed_process(self, mock_sub):
        """Should return a CompletedProcess result."""
        mock_sub.return_value = MagicMock(returncode=0, stdout="Playing", stderr="")
        result = tpc.run_playerctl("status")
        self.assertEqual(result, "Playing")
        mock_sub.assert_called_once()


class TestCheckPlayerctl(unittest.TestCase):
    """Test check_playerctl() - verifies playerctl command exists."""

    @patch.object(tpc, "_playerctl_subprocess")
    def test_playerctl_exists_ok(self, mock_sub):
        """When playerctl --version succeeds, no error."""
        mock_sub.return_value = MagicMock(returncode=0, stdout="playerctl 2.12.0")
        tpc.check_playerctl()  # Should not raise

    @patch.object(tpc, "_playerctl_subprocess")
    def test_playerctl_missing_exits(self, mock_sub):
        """When playerctl is missing, exits with error."""
        mock_sub.return_value = MagicMock(returncode=127, stdout="", stderr="")
        with self.assertRaises(SystemExit) as cm:
            tpc.check_playerctl()
        self.assertEqual(cm.exception.code, 1)


class TestConfigNoBG(unittest.TestCase):
    """Test Config - BG should no longer be in Config."""

    def test_config_no_bg(self):
        """Config should not have BG attribute."""
        self.assertFalse(hasattr(tpc.Config, "BG"))


class TestResetState(unittest.TestCase):
    """Test that dead code has been removed."""

    def test_no_cursor_move_pattern(self):
        """CURSOR_MOVE_PATTERN should be removed (unused)."""
        self.assertFalse(hasattr(tpc, "CURSOR_MOVE_PATTERN"))


class TestResetStateFull(unittest.TestCase):
    """Test reset_state() - resets player state."""

    def setUp(self):
        self._orig = tpc.state
        tpc.state = tpc.PlayerState()

    def tearDown(self):
        tpc.state = self._orig

    def test_resets_title(self):
        """Should reset title to empty string."""
        tpc.state.title = "Old Title"
        tpc.reset_state()
        self.assertEqual(tpc.state.title, "")

    def test_resets_artist(self):
        """Should reset artist to empty string."""
        tpc.state.artist = "Old Artist"
        tpc.reset_state()
        self.assertEqual(tpc.state.artist, "")

    def test_resets_album(self):
        """Should reset album to empty string."""
        tpc.state.album = "Old Album"
        tpc.reset_state()
        self.assertEqual(tpc.state.album, "")

    def test_resets_position(self):
        """Should reset position to 0."""
        tpc.state.position = 100.0
        tpc.reset_state()
        self.assertEqual(tpc.state.position, 0.0)

    def test_resets_status(self):
        """Should reset status to 'No player'."""
        tpc.state.status = "Playing"
        tpc.reset_state()
        self.assertEqual(tpc.state.status, "No player")

    def test_sets_dirty_true(self):
        """Should set dirty to True."""
        tpc.state.dirty = False
        tpc.reset_state()
        self.assertTrue(tpc.state.dirty)

    def test_resets_pre_mute_volume(self):
        """Should reset pre_mute_volume to default (50)."""
        tpc.state.pre_mute_volume = 75
        tpc.reset_state()
        self.assertEqual(tpc.state.pre_mute_volume, 50)

    def test_uses_fresh_player_state(self):
        """reset_state() creates a fresh PlayerState to avoid stale fields."""
        tpc.state.title = "Old Title"
        tpc.state.pre_mute_volume = 75
        tpc.state.artist = "Old Artist"
        tpc.reset_state()
        # All fields should match fresh PlayerState defaults
        fresh = tpc.PlayerState()
        self.assertEqual(tpc.state.title, fresh.title)
        self.assertEqual(tpc.state.pre_mute_volume, fresh.pre_mute_volume)
        self.assertEqual(tpc.state.artist, fresh.artist)
        self.assertEqual(tpc.state.status, "No player")  # reset_state sets this


if __name__ == "__main__":
    unittest.main(verbosity=2)
