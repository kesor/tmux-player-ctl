#!/usr/bin/env python3
"""Test that two headers written consecutively don't concatenate."""

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


class TestHeaderDoubleRender(unittest.TestCase):
    """Test that headers don't have extra borders when rendered consecutively."""

    def setUp(self):
        self._orig_state = tpc.s.state
        tpc.s.state = tpc.PlayerState()

    def tearDown(self):
        tpc.s.state = self._orig_state

    def test_single_header_no_extra_border(self):
        """A single header should have exactly 2 border characters."""
        tpc.s.state.status = "Playing"
        tpc.s.state.player = "spotifyd"
        tpc.s.available_players = ["spotifyd"]

        result = tpc.header_row()
        visible = strip_visible(result)

        border_count = visible.count("│")
        self.assertEqual(
            border_count, 2, f"Header should have 2 borders, got {border_count}: {repr(visible)}"
        )

    def test_empty_header_no_extra_border(self):
        """Empty header should also have exactly 2 border characters."""
        tpc.s.state.status = ""
        tpc.s.state.player = ""
        tpc.s.available_players = []

        result = tpc.header_row()
        visible = strip_visible(result)

        border_count = visible.count("│")
        self.assertEqual(
            border_count, 2, f"Header should have 2 borders, got {border_count}: {repr(visible)}"
        )

    def test_headers_are_same_width(self):
        """Both empty and populated headers should have the same visible width."""
        # Empty header
        tpc.s.state.status = ""
        tpc.s.state.player = ""
        tpc.s.available_players = []
        h1 = tpc.header_row()
        v1 = strip_visible(h1)

        # Populated header
        tpc.s.state.status = "Playing"
        tpc.s.state.player = "spotifyd"
        tpc.s.available_players = ["spotifyd"]
        h2 = tpc.header_row()
        v2 = strip_visible(h2)

        self.assertEqual(len(v1), len(v2), f"Headers should be same width: {len(v1)} vs {len(v2)}")


if __name__ == "__main__":
    unittest.main(verbosity=2)