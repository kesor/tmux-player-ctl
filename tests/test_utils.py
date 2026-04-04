#!/usr/bin/env python3
"""
Test suite for utility functions.
"""

import unittest

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


class TestFormatTimeTotal(unittest.TestCase):
    """Test format_time_total() - formats track length."""

    def setUp(self):
        self._orig_state = tpc.state
        tpc.state = tpc.PlayerState()

    def tearDown(self):
        tpc.state = self._orig_state

    def test_zero_seconds(self):
        """Zero returns 0:00."""
        result = tpc.format_time_total(0)
        self.assertEqual(result, "0:00")

    def test_negative_returns_zero(self):
        """Negative returns 0:00."""
        result = tpc.format_time_total(-10)
        self.assertEqual(result, "0:00")

    def test_seconds_only(self):
        """Under a minute shows M:SS."""
        result = tpc.format_time_total(45)
        self.assertEqual(result, "0:45")

    def test_one_minute(self):
        """One minute shows 1:00."""
        result = tpc.format_time_total(60)
        self.assertEqual(result, "1:00")

    def test_minutes_and_seconds(self):
        """Shows M:SS format."""
        result = tpc.format_time_total(125)  # 2:05
        self.assertEqual(result, "2:05")

    def test_one_hour(self):
        """One hour shows H:MM:SS."""
        result = tpc.format_time_total(3600)  # 1:00:00
        self.assertEqual(result, "1:00:00")

    def test_long_track(self):
        """Long track shows H:MM:SS."""
        result = tpc.format_time_total(3723)  # 1:02:03
        self.assertEqual(result, "1:02:03")


class TestTimeWidth(unittest.TestCase):
    """Test time_width() - calculates time display width."""

    def setUp(self):
        self._orig_state = tpc.state
        tpc.state = tpc.PlayerState()

    def tearDown(self):
        tpc.state = self._orig_state

    def test_zero_length_returns_minimum(self):
        """Zero length returns minimum width."""
        tpc.state.length = 0
        result = tpc.time_width()
        self.assertEqual(result, 5)  # minimum "0:00"

    def test_short_track(self):
        """Short track width."""
        tpc.state.length = 300  # 5:00
        result = tpc.time_width()
        self.assertEqual(result, 4)  # "5:00"

    def test_long_track(self):
        """Long track (doesn't show hours in format_time)."""
        tpc.state.length = 3600  # 1:00:00
        result = tpc.time_width()
        # format_time shows MM:SS, so 60:00 = 5 chars
        self.assertEqual(result, 5)  # "60:00"


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


class TestResetState(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
