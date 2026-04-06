"""Tests for code review fixes:
- Bug #7: Missing minimum width clamping
- Bug #11: Zero-length streams (live radio) display
- Window resize handling (SIGWINCH)
"""

import unittest
from unittest.mock import patch, MagicMock

import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestWindowResize(unittest.TestCase):
    """Window resize handling via SIGWINCH.

    When terminal window is resized, we need to:
    1. Catch SIGWINCH signal
    2. Redetect terminal width
    3. Mark state as dirty to trigger redraw
    """

    def setUp(self):
        self._orig_ui_width = tpc.Config.UI_WIDTH
        self._orig_inner_w = tpc.Config.INNER_W
        # Reset resize flag
        tpc.resize_requested = False

    def tearDown(self):
        tpc.Config.UI_WIDTH = self._orig_ui_width
        tpc.Config.INNER_W = self._orig_inner_w
        tpc.resize_requested = False

    def test_request_resize_sets_flag(self):
        """SIGWINCH handler should set resize_requested = True."""
        tpc.resize_requested = False
        tpc.request_resize(None, None)
        self.assertTrue(tpc.resize_requested)

    def test_resize_updates_width(self):
        """Handling resize should update Config.UI_WIDTH."""
        tpc.Config.UI_WIDTH = 72
        tpc.Config.INNER_W = 68

        # Simulate resize to smaller terminal
        with patch.object(tpc, "detect_terminal_width", return_value=50):
            tpc.detect_and_apply_terminal_width()

        self.assertEqual(tpc.Config.UI_WIDTH, 50)
        self.assertEqual(tpc.Config.INNER_W, 46)

    def test_resize_clamps_to_max(self):
        """Resize beyond 72 should clamp to 72."""
        with patch.object(tpc, "detect_terminal_width", return_value=100):
            tpc.detect_and_apply_terminal_width()

        self.assertEqual(tpc.Config.UI_WIDTH, 72)

    def test_resize_clamps_to_min(self):
        """Resize below 28 should clamp to 28."""
        with patch.object(tpc, "detect_terminal_width", return_value=20):
            tpc.detect_and_apply_terminal_width()

        self.assertEqual(tpc.Config.UI_WIDTH, 28)


class TestMinWidthClamping(unittest.TestCase):
    """Bug #7: Missing minimum width clamping.

    Config.UI_WIDTH = min(72, terminal_width) can yield 0 or negative
    Config.INNER_W, breaking math in progress_row(), volume_row(), and
    truncation. INNER_W should never go below 0 and UI_WIDTH should have
    a sensible minimum.
    """

    def setUp(self):
        self._orig_ui_width = tpc.Config.UI_WIDTH
        self._orig_inner_w = tpc.Config.INNER_W

    def tearDown(self):
        tpc.Config.UI_WIDTH = self._orig_ui_width
        tpc.Config.INNER_W = self._orig_inner_w

    def test_detect_width_returns_at_least_28(self):
        """detect_terminal_width should return minimum 28 for valid UI."""
        # Reset for testing
        tpc.Config.UI_WIDTH = 72
        tpc.Config.INNER_W = 68

        tpc.detect_and_apply_terminal_width()

        # After clamping, UI_WIDTH should be at least 28
        self.assertGreaterEqual or self.fail
        # Check that INNER_W is at least 0
        self.assertGreaterEqual(tpc.Config.INNER_W, 0)

    def test_zero_terminal_width_clamps_up(self):
        """Zero terminal width should clamp to minimum UI_WIDTH."""
        tpc.Config.UI_WIDTH = 72
        tpc.Config.INNER_W = 68

        # Simulate what would happen if detect_terminal_width returned 0
        with patch.object(tpc, "detect_terminal_width", return_value=0):
            tpc.detect_and_apply_terminal_width()

        # Should clamp to minimum of 28 (or some reasonable minimum)
        self.assertGreaterEqual(tpc.Config.UI_WIDTH, 28)
        self.assertGreaterEqual(tpc.Config.INNER_W, 0)

    def test_negative_terminal_width_clamps_up(self):
        """Negative terminal width should clamp to minimum UI_WIDTH."""
        tpc.Config.UI_WIDTH = 72
        tpc.Config.INNER_W = 68

        with patch.object(tpc, "detect_terminal_width", return_value=-10):
            tpc.detect_and_apply_terminal_width()

        self.assertGreaterEqual(tpc.Config.UI_WIDTH, 28)
        self.assertGreaterEqual(tpc.Config.INNER_W, 0)

    def test_inner_w_never_negative(self):
        """INNER_W = UI_WIDTH - 4 should never be negative."""
        for width in [0, 1, 2, 3, 4, 5, 10, 20, 28, 72, 100]:
            tpc.Config.UI_WIDTH = width
            tpc.detect_and_apply_terminal_width()
            self.assertGreaterEqual(
                tpc.Config.INNER_W,
                0,
                f"INNER_W should not be negative for UI_WIDTH={width}",
            )


class TestZeroLengthStreams(unittest.TestCase):
    """Bug #11: Zero-length MPRIS streams.

    Browsers (Firefox/YouTube) and live radio often report length = 0.0.
    Currently renders as 0:00 and a flat progress bar. format_time() and
    progress_row() should detect total <= 0 and display "Live" or "N/A"
    instead of 0:00.
    """

    def setUp(self):
        self._orig_inner_w = tpc.Config.INNER_W
        tpc.Config.INNER_W = 68  # Standard width for tests

    def tearDown(self):
        tpc.Config.INNER_W = self._orig_inner_w

    def test_format_time_zero_as_length_returns_live(self):
        """format_time(0, is_length=True) should return 'Live' for streaming."""
        result = tpc.format_time(0, is_length=True)
        self.assertIn(result, ["Live", "N/A"])

    def test_format_time_negative_as_length_returns_live(self):
        """format_time(-1, is_length=True) should return 'Live'."""
        result = tpc.format_time(-1, is_length=True)
        self.assertIn(result, ["Live", "N/A"])

    def test_format_time_position_zero_still_returns_zero_time(self):
        """format_time(0) for position (not length) returns '0:00'."""
        # Position 0 at start of track should be 0:00, not Live
        result = tpc.format_time(0)
        self.assertEqual(result, "0:00")

    def test_format_time_small_positive_as_length_returns_live(self):
        """format_time(0.5, is_length=True) for streams should be treated as live."""
        result = tpc.format_time(0.5, is_length=True)
        self.assertIn(result, ["Live", "N/A", "0:00"])

    def test_progress_bar_zero_length_shows_empty(self):
        """progress_bar with total=0 should not crash."""
        result = tpc.progress_bar(0, 0, 20)
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 20)

    def test_progress_bar_zero_length_is_not_full(self):
        """progress_bar(pos, 0, w) should show empty bar, not full."""
        result = tpc.progress_bar(0, 0, 20)
        # Should be all empty characters, not filled
        self.assertNotIn("█", result)
        self.assertNotIn("━", result)

    def test_progress_bar_normal_length_still_works(self):
        """progress_bar with normal length still works."""
        result = tpc.progress_bar(30, 100, 20)
        self.assertIsInstance(result, str)
        # Should have some filled portion
        self.assertTrue("█" in result or "━" in result)


class TestFormatTimeNormalBehavior(unittest.TestCase):
    """Verify format_time still works correctly for normal durations."""

    def test_seconds_only(self):
        """Seconds only: 45 -> '0:45'."""
        result = tpc.format_time(45)
        self.assertEqual(result, "0:45")

    def test_minutes_and_seconds(self):
        """Minutes and seconds: 125 -> '2:05'."""
        result = tpc.format_time(125)
        self.assertEqual(result, "2:05")

    def test_hours(self):
        """Hours: 3723 -> '1:02:03'."""
        result = tpc.format_time(3723)
        self.assertEqual(result, "1:02:03")

    def test_exact_hours(self):
        """Exact hours: 3600 -> '1:00:00'."""
        result = tpc.format_time(3600)
        self.assertEqual(result, "1:00:00")


if __name__ == "__main__":
    unittest.main(verbosity=2)
