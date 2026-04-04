#!/usr/bin/env python3

import unittest

import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestFormatTimeTotal(unittest.TestCase):
    """Test format_time() - formats track length."""

    def test_zero_seconds(self):
        """Zero returns 0:00."""
        result = tpc.format_time(0)
        self.assertEqual(result, "0:00")

    def test_negative_returns_zero(self):
        """Negative returns 0:00."""
        result = tpc.format_time(-10)
        self.assertEqual(result, "0:00")

    def test_seconds_only(self):
        """Under a minute shows M:SS."""
        result = tpc.format_time(45)
        self.assertEqual(result, "0:45")

    def test_one_minute(self):
        """One minute shows 1:00."""
        result = tpc.format_time(60)
        self.assertEqual(result, "1:00")

    def test_minutes_and_seconds(self):
        """Shows M:SS format."""
        result = tpc.format_time(125)  # 2:05
        self.assertEqual(result, "2:05")

    def test_one_hour(self):
        """One hour shows H:MM:SS."""
        result = tpc.format_time(3600)  # 1:00:00
        self.assertEqual(result, "1:00:00")

    def test_long_track(self):
        """Long track shows H:MM:SS."""
        result = tpc.format_time(3723)  # 1:02:03
        self.assertEqual(result, "1:02:03")
