"""Tests for Theme refactoring to RGB triplets.

Bug: Theme constants include ANSI sequences instead of just RGB values.
They should be r;g;b triplets, with ANSI added at point of use.
"""

import unittest
import re

import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestThemeValuesAreRGB(unittest.TestCase):
    """Verify Theme constants are RGB triplets, not ANSI sequences."""

    def test_playing_is_rgb_not_ansi(self):
        """Theme.PLAYING should be r;g;b format, not \\033[38;2;...m"""
        self.assertNotIn("\033", tpc.Theme.PLAYING, 
            "Theme.PLAYING should be RGB, not ANSI sequence")
        self.assertIn(";", tpc.Theme.PLAYING,
            "Theme.PLAYING should contain semicolons for RGB")
        # Should be "R;G;B" format
        parts = tpc.Theme.PLAYING.split(";")
        self.assertEqual(len(parts), 3, 
            "Theme.PLAYING should have 3 parts: R;G;B")

    def test_vol_low_is_rgb_not_ansi(self):
        """Theme.VOL_LOW should be r;g;b format"""
        self.assertNotIn("\033", tpc.Theme.VOL_LOW,
            "Theme.VOL_LOW should be RGB, not ANSI sequence")
        parts = tpc.Theme.VOL_LOW.split(";")
        self.assertEqual(len(parts), 3)

    def test_all_theme_colors_are_rgb(self):
        """All color Theme constants should be RGB triplets."""
        color_attrs = [
            'PLAYING', 'PAUSED', 'STOPPED', 'RECORDING',
            'KEY_HINT', 'BORDER', 'DIM',
            'PROGRESS_FILL', 'PROGRESS_EMPTY',
            'VOL_MUTED', 'VOL_LOW', 'VOL_MED', 'VOL_HIGH', 'VOL_EMPTY',
        ]
        for attr in color_attrs:
            val = getattr(tpc.Theme, attr)
            self.assertNotIn("\033", val,
                f"Theme.{attr} should be RGB, not ANSI: {repr(val)}")
            parts = val.split(";")
            self.assertEqual(len(parts), 3,
                f"Theme.{attr} should be R;G;B: {repr(val)}")


class TestAnsiHelpersExist(unittest.TestCase):
    """Verify Ansi class exists with required methods."""

    def test_ansi_class_exists(self):
        """Should have Ansi class with static methods."""
        self.assertTrue(hasattr(tpc, 'Ansi'), "Need Ansi class")

    def test_ansi_fg_method_exists(self):
        """Ansi.fg() static method should exist."""
        self.assertTrue(hasattr(tpc.Ansi, 'fg'))

    def test_ansi_bg_method_exists(self):
        """Ansi.bg() static method should exist."""
        self.assertTrue(hasattr(tpc.Ansi, 'bg'))

    def test_ansi_fg_bg_method_exists(self):
        """Ansi.fg_bg() static method should exist."""
        self.assertTrue(hasattr(tpc.Ansi, 'fg_bg'))

    def test_ansi_fg_returns_correct_format(self):
        """Ansi.fg should return \\033[38;2;RGB;m format."""
        result = tpc.Ansi.fg("166;227;161")
        self.assertEqual(result, "\033[38;2;166;227;161m")

    def test_ansi_bg_returns_correct_format(self):
        """Ansi.bg should return \\033[48;2;RGB;m format."""
        result = tpc.Ansi.bg("166;227;161")
        self.assertEqual(result, "\033[48;2;166;227;161m")

    def test_ansi_fg_bg_returns_correct_format(self):
        """Ansi.fg_bg should return FG+BG combined format."""
        result = tpc.Ansi.fg_bg("166;227;161", "30;30;46")
        self.assertEqual(result, "\033[38;2;166;227;161m\033[48;2;30;30;46m")

    def test_ansi_reset_works(self):
        """Ansi.RESET_ALL should be \\033[0m"""
        self.assertEqual(tpc.Ansi.RESET_ALL, "\033[0m")


class TestColorizeWorks(unittest.TestCase):
    """Verify colorize() function still works with new theme."""

    def test_colorize_produces_correct_ansi(self):
        """colorize should wrap text in correct ANSI sequence."""
        result = tpc.colorize("test", tpc.Theme.PLAYING)
        # Should start with FG ANSI and end with RESET
        self.assertTrue(result.startswith("\033[38;2;"),
            f"Should start with FG ANSI: {repr(result)}")
        self.assertTrue(result.endswith(f"test\033[0m"),
            f"Should end with RESET: {repr(result)}")


class TestVolumeBarStillWorks(unittest.TestCase):
    """Verify volume_bar still renders correctly after refactoring."""

    def setUp(self):
        tpc.Config.INNER_W = 68

    def test_volume_bar_renders(self):
        """volume_bar should render without errors."""
        result = tpc.volume_bar(50, 50)
        self.assertIsNotNone(result)
        self.assertIn("█", result)
        self.assertIn("░", result)

    def test_volume_bar_has_minimal_sequences(self):
        """volume_bar should still emit minimal ANSI sequences."""
        result = tpc.volume_bar(50, 50)
        sequences = re.findall(r'\x1b\[[0-9;]+m', result)
        self.assertLessEqual(len(sequences), 10,
            f"Too many sequences: {len(sequences)}")


if __name__ == "__main__":
    unittest.main(verbosity=2)