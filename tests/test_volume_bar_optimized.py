"""Tests for volume_bar ANSI sequence optimization.

Bug #10: volume_bar() emits too many ANSI sequences.
Should emit one sequence per color zone change, not one per character.
"""

import unittest
import re

import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestVolumeBarSequenceCount(unittest.TestCase):
    """Test that volume_bar emits minimal ANSI sequences."""

    def setUp(self):
        tpc.Config.INNER_W = 68

    def test_full_volume_has_few_sequences(self):
        """Full volume (100%) should emit minimal ANSI sequences."""
        result = tpc.volume_bar(100, 50)
        sequences = re.findall(r"\x1b\[[0-9;]+m", result)
        # Optimized: 9 sequences max (green, yellow+BG, yellow, red+BG, red, reset + BG restore)
        # Before optimization: 53 sequences
        self.assertLessEqual(
            len(sequences),
            9,
            f"Too many ANSI sequences: {len(sequences)}. Should be <= 9.",
        )

    def test_half_volume_has_few_sequences(self):
        """Volume 50% should emit minimal ANSI sequences."""
        result = tpc.volume_bar(50, 50)
        sequences = re.findall(r"\x1b\[[0-9;]+m", result)
        # Optimized: green, yellow+BG, yellow, reset = ~4-5 sequences
        # Before optimization: 101 sequences
        self.assertLessEqual(
            len(sequences),
            6,
            f"Too many ANSI sequences: {len(sequences)}. Should be <= 6.",
        )

    def test_low_volume_has_few_sequences(self):
        """Volume 25% (all green) should emit minimal ANSI sequences."""
        result = tpc.volume_bar(25, 50)
        sequences = re.findall(r"\x1b\[[0-9;]+m", result)
        # Optimized: green, empty+BG, reset = ~4 sequences
        # Before optimization: 127 sequences
        self.assertLessEqual(
            len(sequences),
            5,
            f"Too many ANSI sequences: {len(sequences)}. Should be <= 5.",
        )

    def test_zero_volume_has_minimal_sequences(self):
        """Volume 0% should emit minimal sequences."""
        result = tpc.volume_bar(0, 50)
        sequences = re.findall(r"\x1b\[[0-9;]+m", result)
        # If Theme.BG is set: 4 sequences (FG, BG, reset, BG restore)
        # Otherwise: 3 sequences (FG, BG, reset)
        expected = 4 if tpc.Theme.BG else 3
        self.assertEqual(
            len(sequences), expected, f"Expected {expected} sequences: {len(sequences)}"
        )

    def test_wide_bar_still_has_few_sequences(self):
        """Wide bar (68 chars) should still have few sequences."""
        result = tpc.volume_bar(65, 68)
        sequences = re.findall(r"\x1b\[[0-9;]+m", result)
        # Still much better than original ~118 sequences
        self.assertLessEqual(
            len(sequences),
            10,
            f"Too many ANSI sequences: {len(sequences)}. Should be <= 10.",
        )


class TestVolumeBarContent(unittest.TestCase):
    """Test that optimized volume_bar still renders correctly."""

    def setUp(self):
        tpc.Config.INNER_W = 68

    def test_zero_volume_all_empty_blocks(self):
        """Volume 0% should be all empty blocks."""
        result = tpc.volume_bar(0, 20)
        # Should have no filled blocks
        self.assertNotIn("█", result)
        self.assertNotIn("▓", result)
        # Should have empty blocks
        self.assertIn("░", result)

    def test_full_volume_has_filled_blocks(self):
        """Volume 100% should be all filled blocks."""
        result = tpc.volume_bar(100, 50)
        # Should be all filled (no empty blocks)
        self.assertNotIn("░", result)
        self.assertIn("█", result)

    def test_correct_total_width(self):
        """Volume bar should be correct total width (without ANSI)."""
        result = tpc.volume_bar(50, 30)
        # Strip ANSI codes and check visible length
        plain = re.sub(r"\x1b\[[0-9;]+m", "", result)
        self.assertEqual(len(plain), 30)


class TestVolumeBarAlignment(unittest.TestCase):
    """Test that volume bar aligns with progress bar."""

    def setUp(self):
        self._orig_inner_w = tpc.Config.INNER_W
        tpc.Config.INNER_W = 68

    def tearDown(self):
        tpc.Config.INNER_W = self._orig_inner_w

    def test_volume_bar_matches_progress_bar_width(self):
        """Volume bar and progress bar should have exactly the same width.

        This ensures the bars start and end at the same columns,
        creating a clean visual alignment.
        """
        # Simulate a track with times like '24:38' and '31:27'
        tpc.s.state._start_time_w = 5
        tpc.s.state._end_time_w = 5
        tpc.s.state.position = 1478  # 24:38
        tpc.s.state.length = 1887  # 31:27
        tpc.s.state.volume = 100

        # Get the progress bar width (from progress_row)
        start_w = tpc.s.state._start_time_w
        end_w = tpc.s.state._end_time_w
        progress_bar_w = tpc.Config.INNER_W - start_w - 1 - 1 - end_w

        # Build progress bar
        progress_bar = tpc.progress_bar(
            tpc.s.state.position, tpc.s.state.length, progress_bar_w
        )
        progress_bar_visible = tpc.visible_width(progress_bar)

        # Get the volume bar (from volume_row calculation)
        vol_pct = tpc.s.state.volume
        pct_text = f"{vol_pct}%"
        vol_icon = f" {tpc.icon(tpc._volume_icon(vol_pct))} "
        icon_w = tpc.visible_width(vol_icon)
        bar_w = tpc.Config.INNER_W - icon_w - 1 - 1 - len(pct_text)

        # The row total needs to equal INNER_W
        # icon + gap + bar + gap + pct = INNER_W
        # bar_w should be adjusted so total matches
        total_slots = icon_w + 1 + progress_bar_w + 1 + len(pct_text)
        extra = tpc.Config.INNER_W - total_slots
        # icon_w gets the extra space
        icon_w += extra

        volume_bar = tpc.volume_bar(vol_pct, progress_bar_w)
        volume_bar_visible = tpc.visible_width(volume_bar)

        # Both bars should have the same visible width
        self.assertEqual(
            progress_bar_visible,
            volume_bar_visible,
            f"Progress bar width ({progress_bar_visible}) != volume bar width ({volume_bar_visible})",
        )
        self.assertEqual(progress_bar_visible, progress_bar_w)
        self.assertEqual(volume_bar_visible, progress_bar_w)


if __name__ == "__main__":
    unittest.main(verbosity=2)
