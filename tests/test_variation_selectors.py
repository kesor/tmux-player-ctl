#!/usr/bin/env python3
"""Test that visible_width handles variation selectors correctly."""

import unittest
import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestVisibleWidthVariationSelectors(unittest.TestCase):
    """Test that visible_width handles variation selectors correctly."""

    def test_variation_selector_not_counted(self):
        """Variation selectors (U+FE00-U+FE0F) should have zero width."""
        # The pause icon includes U+FE0E (variation selector)
        pause_icon = "\u23f8\ufe0e"  # ⏸
        
        # Should count as 1, not 2
        width = tpc.visible_width(pause_icon)
        self.assertEqual(width, 1, 
            f"Pause icon should be width 1, got {width}")

    def test_playing_icon_width(self):
        """Playing icon should be width 1."""
        playing_icon = "\u23f5\ufe0e"  # ▶
        width = tpc.visible_width(playing_icon)
        self.assertEqual(width, 1)

    def test_stopped_icon_width(self):
        """Stopped icon should be width 1."""
        stopped_icon = "\u23f9\ufe0e"  # ⏹
        width = tpc.visible_width(stopped_icon)
        self.assertEqual(width, 1)

    def test_recording_icon_width(self):
        """Recording icon should be width 1."""
        recording_icon = "\u23fa\ufe0e"  # ⏺
        width = tpc.visible_width(recording_icon)
        self.assertEqual(width, 1)

    def test_status_text_with_icon(self):
        """Status text with icon should count icon as 1 char."""
        # "⏸  paused" should be width 9 (icon=1 + 2 spaces + 6 text)
        status_text = "\u23f8\ufe0e  paused"
        width = tpc.visible_width(status_text)
        # icon(1) + space(1) + space(1) + paused(6) = 9
        self.assertEqual(width, 9)

    def test_emoji_with_variation_selector(self):
        """Variation selectors after emoji should not add width."""
        # Baseball emoji with text variation selector
        base = "\U000026BE"  # ⚾
        with_var = "\U000026BE\uFE0E"  # ⚾︎
        
        base_width = tpc.visible_width(base)
        var_width = tpc.visible_width(with_var)
        
        # Should be the same width
        self.assertEqual(var_width, base_width,
            f"With var selector: {var_width}, base: {base_width}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
