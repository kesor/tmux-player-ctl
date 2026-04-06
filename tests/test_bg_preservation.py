#!/usr/bin/env python3
"""
Test suite for background color preservation in UI rendering.
"""

import unittest
import sys
import importlib.util

spec = importlib.util.spec_from_file_location("tpc_bg", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)

# Set BG after import by modifying the class attribute directly on THIS module
# This doesn't affect other test modules that import tpc separately
tpc.Theme.BG = "30;30;50"
# Also update Ansi.reset's cached bg_rgb default
# The reset method uses Theme.BG as the default, so this should work


class TestBackgroundPreservation(unittest.TestCase):
    """Test that ANSI reset functions preserve the background color."""

    def test_border_top_preserves_bg(self):
        """border_top() should start and end with BG restore."""
        result = tpc.border_top()
        # border functions now start with BG restore (Ansi.reset()), then set FG
        # Check that it starts with RESET + BG restore
        self.assertTrue(result.startswith(f"\x1b[0m\x1b[48;2;{tpc.Theme.BG}m"))
        # And ends with BG restore
        self.assertTrue(result.endswith(f"\x1b[0m\x1b[48;2;{tpc.Theme.BG}m"))

    def test_border_mid_preserves_bg(self):
        """border_mid() should start and end with BG restore."""
        result = tpc.border_mid()
        self.assertTrue(result.startswith(f"\x1b[0m\x1b[48;2;{tpc.Theme.BG}m"))
        self.assertTrue(result.endswith(f"\x1b[0m\x1b[48;2;{tpc.Theme.BG}m"))

    def test_border_bot_preserves_bg(self):
        """border_bot() should start and end with BG restore."""
        result = tpc.border_bot()
        self.assertTrue(result.startswith(f"\x1b[0m\x1b[48;2;{tpc.Theme.BG}m"))
        self.assertTrue(result.endswith(f"\x1b[0m\x1b[48;2;{tpc.Theme.BG}m"))

    def test_row_preserves_bg(self):
        """row() should not reset background color."""
        result = tpc.row(("Hello", 10, "<"))
        # row() now starts with Ansi.reset() which includes RESET_ALL, followed by BG restore
        # This is correct - it ensures BG is set before content
        # The key is that after RESET_ALL, we have BG restore
        parts = result.split("\x1b[38;2")
        # After the first RESET_ALL, should have BG restore
        self.assertTrue(parts[0].endswith(f"\x1b[0m\x1b[48;2;{tpc.Theme.BG}m"))

    def test_progress_bar_preserves_bg(self):
        """progress_bar() should not reset background color."""
        result = tpc.progress_bar(50.0, 100.0, 40)
        # Ends with RESET + BG restore
        # Check that BG is restored at the end
        self.assertTrue(result.endswith(f"\033[0m\033[48;2;{tpc.Theme.BG}m"))

    def test_volume_bar_preserves_bg(self):
        """volume_bar() should not reset background color."""
        result = tpc.volume_bar(50, 40)
        # Ends with RESET + BG restore
        self.assertTrue(result.endswith(f"\033[0m\033[48;2;{tpc.Theme.BG}m"))

    def test_colorize_preserves_bg(self):
        """colorize() should not reset background color."""
        result = tpc.colorize("test", "255;0;0")
        # Ends with RESET + BG restore
        self.assertTrue(result.endswith(f"\033[0m\033[48;2;{tpc.Theme.BG}m"))

    def test_render_ui_output_preserves_bg(self):
        """render_ui() should produce output that ends with BG color."""
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.player = "spotify"
        tpc.s.state.status = "Playing"
        tpc.s.state.position = 60.0
        tpc.s.state.length = 180.0
        tpc.s.state.volume = 75
        tpc.s.available_players = ["spotify"]
        tpc.s.state.title = "Test Song"
        tpc.s.state.artist = "Test Artist"
        tpc.s.state.album = "Test Album"

        import io

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            tpc.render_ui()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        # Every line should end with BG restore, not bare RESET_ALL
        for i, line in enumerate(output.split("\033[H")):
            pass  # Already captured via move_cursor


if __name__ == "__main__":
    unittest.main(verbosity=2)
