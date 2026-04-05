"""Display utility tests: clear_screen, move_cursor."""

import unittest
from io import StringIO
from unittest.mock import patch

import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestClearScreen(unittest.TestCase):
    """Test clear_screen() writes ANSI escape sequences."""

    def test_writes_clear_escape(self):
        """Should write \\033[2J\\033[H to clear screen."""
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            tpc.clear_screen()
            output = mock_out.getvalue()
            self.assertIn("\033[2J", output)
            self.assertIn("\033[H", output)

    def test_writes_background_when_set(self):
        """Should write background color escape when Theme.BG is set."""
        orig_bg = tpc.Theme.BG
        tpc.Theme.BG = "255;0;0"
        try:
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                tpc.clear_screen()
                output = mock_out.getvalue()
                self.assertIn("\033[48;2;255;0;0m", output)
        finally:
            tpc.Theme.BG = orig_bg

    def test_clears_dirty_flag(self):
        """Should reset dirty flag after clearing."""
        tpc.s.state.dirty = True
        with patch("sys.stdout", new_callable=StringIO):
            tpc.clear_screen()
        self.assertFalse(tpc.s.state.dirty)


class TestMoveCursor(unittest.TestCase):
    """Test move_cursor() positions cursor with ANSI escape."""

    def test_writes_csi_sequence(self):
        """Should write \\033[row;colH escape sequence."""
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            tpc.move_cursor(5, 10)
            output = mock_out.getvalue()
            self.assertEqual(output, "\033[5;10H")


if __name__ == "__main__":
    unittest.main(verbosity=2)
