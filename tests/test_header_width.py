#!/usr/bin/env python3
"""Test header row width - CJK handling and slot alignment."""

import unittest
import re

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def strip_visible(text):
    """Remove ANSI codes."""
    return ANSI.sub("", text)


import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestHeaderRowWidth(unittest.TestCase):
    """Test header_row() produces correct width rows."""

    def setUp(self):
        self._orig_state = tpc.s.state
        tpc.s.state = tpc.PlayerState()
        tpc.s.last_command_time = 0

    def tearDown(self):
        tpc.s.state = self._orig_state

    def test_pad_visible_produces_correct_width(self):
        """pad_visible should produce text with exactly the specified visible width."""
        text = "hello"  # 5 visible chars
        result = tpc.pad_visible(text, 10, "<")
        self.assertEqual(
            tpc.visible_width(result), 10, f"pad_visible to width 10: {repr(result)}"
        )

    def test_pad_visible_exact_fit(self):
        """pad_visible with text matching width should return text unchanged."""
        text = "hello"
        result = tpc.pad_visible(text, 5, "<")
        self.assertEqual(result, text)

    def test_row_combines_slots_with_gaps(self):
        """row() with 3 slots produces content with correct total width."""
        result = tpc.row(
            ("aaa", 12, "<"),
            ("bbb", 45, "^"),
            ("ccc", 9, ">"),
        )
        visible = strip_visible(result)
        # Content: slot1(12) + space(1) + slot2(45) + space(1) + slot3(9) = 68
        # Total with row format: │ space(1) + content(68) + space(1) + │ = 72
        # Use visible_width to account for any combining characters
        self.assertEqual(tpc.visible_width(visible), 72)

    def test_header_width_with_single_player(self):
        """Header with single player (no switch) should have correct width."""
        tpc.s.state.status = "Playing"
        tpc.s.state.player = "spotifyd"
        tpc.s.available_players = ["spotifyd"]  # single player

        result = tpc.header_row()
        visible = strip_visible(result)

        # With single player, switch is empty but still takes slot width
        # Total should be 72
        self.assertEqual(
            tpc.visible_width(visible),
            72,
            f"Header should be 72 visible chars: {repr(visible)}",
        )

    def test_header_width_empty_state(self):
        """Header with empty state should have correct width."""
        tpc.s.state.status = ""
        tpc.s.state.player = ""
        tpc.s.available_players = []

        result = tpc.header_row()
        visible = strip_visible(result)

        self.assertEqual(
            tpc.visible_width(visible),
            72,
            f"Header should be 72 visible chars: {repr(visible)}",
        )

    def test_pad_visible_cjk_wide_characters(self):
        """pad_visible should correctly handle CJK characters (2 columns each)."""
        # CJK characters are 2 columns wide
        cjk = "プレイヤー"  # 5 chars = 10 visible columns
        text = f" {cjk} "  # 2 spaces + 5 CJK = 12 visible

        result = tpc.pad_visible(text, 45, "^")

        # Should be padded to 45 visible columns
        self.assertEqual(
            tpc.visible_width(result),
            45,
            f"pad_visible with CJK to width 45: {repr(result)}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
