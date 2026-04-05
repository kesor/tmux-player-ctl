#!/usr/bin/env python3
"""Test terminal width detection and clamping."""

import unittest
from unittest.mock import patch
import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestTerminalWidth(unittest.TestCase):
    """Test that UI_WIDTH is clamped to terminal width."""

    def setUp(self):
        # Reset Config to original values
        self._orig_ui_width = tpc.Config.UI_WIDTH
        self._orig_inner_w = tpc.Config.INNER_W

    def tearDown(self):
        # Restore
        tpc.Config.UI_WIDTH = self._orig_ui_width
        tpc.Config.INNER_W = self._orig_inner_w

    def test_detect_terminal_width_function_exists(self):
        """A function to detect terminal width should exist."""
        self.assertTrue(hasattr(tpc, "detect_terminal_width"),
            "detect_terminal_width function should exist")

    def test_detect_terminal_width_returns_integer(self):
        """detect_terminal_width should return an integer."""
        result = tpc.detect_terminal_width()
        self.assertIsInstance(result, int)

    def test_detect_terminal_width_uses_tmux_when_available(self):
        """When TMUX_PANE is set, should query tmux for pane width."""
        with patch.dict("os.environ", {"TMUX_PANE": "%100"}, clear=False):
            result = tpc.detect_terminal_width()
            # Should use tmux, not shutil
            self.assertGreater(result, 0)

    def test_detect_terminal_width_uses_shutil_as_fallback(self):
        """When TMUX_PANE not set, should use shutil.get_terminal_size."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("shutil.get_terminal_size") as mock_size:
                mock_size.return_value = type("Size", (), {"columns": 80})()
                result = tpc.detect_terminal_width()
                self.assertEqual(result, 80)

    def test_clamp_ui_width_to_max_72(self):
        """UI_WIDTH should be clamped to 72 at maximum."""
        with patch.object(tpc, "detect_terminal_width", return_value=100):
            tpc.detect_and_apply_terminal_width()
            self.assertEqual(tpc.Config.UI_WIDTH, 72)

    def test_clamp_ui_width_to_terminal_when_narrower(self):
        """UI_WIDTH should be clamped to terminal width when narrower than 72."""
        with patch.object(tpc, "detect_terminal_width", return_value=50):
            tpc.detect_and_apply_terminal_width()
            self.assertEqual(tpc.Config.UI_WIDTH, 50)

    def test_inner_width_recalculated_after_clamp(self):
        """INNER_W should be recalculated after clamping UI_WIDTH."""
        with patch.object(tpc, "detect_terminal_width", return_value=60):
            tpc.detect_and_apply_terminal_width()
            self.assertEqual(tpc.Config.INNER_W, 56)  # 60 - 4


if __name__ == "__main__":
    unittest.main(verbosity=2)
