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
        sequences = re.findall(r'\x1b\[[0-9;]+m', result)
        # Optimized: 8 sequences max (green, yellow+BG, yellow, red+BG, red, reset)
        # Before optimization: 53 sequences
        self.assertLessEqual(len(sequences), 8,
            f"Too many ANSI sequences: {len(sequences)}. Should be <= 8.")

    def test_half_volume_has_few_sequences(self):
        """Volume 50% should emit minimal ANSI sequences."""
        result = tpc.volume_bar(50, 50)
        sequences = re.findall(r'\x1b\[[0-9;]+m', result)
        # Optimized: green, yellow+BG, yellow, reset = ~4-5 sequences
        # Before optimization: 101 sequences
        self.assertLessEqual(len(sequences), 6,
            f"Too many ANSI sequences: {len(sequences)}. Should be <= 6.")

    def test_low_volume_has_few_sequences(self):
        """Volume 25% (all green) should emit minimal ANSI sequences."""
        result = tpc.volume_bar(25, 50)
        sequences = re.findall(r'\x1b\[[0-9;]+m', result)
        # Optimized: green, empty+BG, reset = ~4 sequences
        # Before optimization: 127 sequences
        self.assertLessEqual(len(sequences), 5,
            f"Too many ANSI sequences: {len(sequences)}. Should be <= 5.")

    def test_zero_volume_has_minimal_sequences(self):
        """Volume 0% should emit minimal sequences (FG + BG + reset = 3)."""
        result = tpc.volume_bar(0, 50)
        sequences = re.findall(r'\x1b\[[0-9;]+m', result)
        # 3 sequences: FG color, BG color, reset
        self.assertEqual(len(sequences), 3,
            f"Expected 3 sequences: {len(sequences)}")

    def test_wide_bar_still_has_few_sequences(self):
        """Wide bar (68 chars) should still have few sequences."""
        result = tpc.volume_bar(65, 68)
        sequences = re.findall(r'\x1b\[[0-9;]+m', result)
        # Still much better than original ~118 sequences
        self.assertLessEqual(len(sequences), 10,
            f"Too many ANSI sequences: {len(sequences)}. Should be <= 10.")


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
        plain = re.sub(r'\x1b\[[0-9;]+m', '', result)
        self.assertEqual(len(plain), 30)


if __name__ == "__main__":
    unittest.main(verbosity=2)
