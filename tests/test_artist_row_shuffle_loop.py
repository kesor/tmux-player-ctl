#!/usr/bin/env python3
"""Test shuffle and loop display in artist row."""

import unittest
from unittest.mock import patch
import re

# Strip all ANSI escape sequences and VS15/VS16 (zero-width variation selectors)
ANSI = re.compile(r"\x1b\[[0-9;]*[mABCDHfHJKsu78]|\x1b[78]")


def strip_visible(text):
    """Remove ANSI codes and VS15/VS16 to get visible length."""
    return (
        ANSI.sub("", text)
        .replace("\ufe0e", "")
        .replace("\ufe0f", "")
        .replace("\u200b", "")
    )


import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestArtistRowShuffleLoop(unittest.TestCase):
    """Test artist row with shuffle and loop display."""

    def setUp(self):
        self._orig = tpc.s.state
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.artist = "Test Artist"
        tpc.s.state.shuffle = "false"
        tpc.s.state.loop = "None"

    def tearDown(self):
        tpc.s.state = self._orig

    def test_artist_row_has_three_sections(self):
        """Artist row should have 3 sections: label, artist name, shuffle/loop."""
        result = tpc.artist_row()
        visible = strip_visible(result)
        # Should have 2 borders (│) for 3 sections
        self.assertEqual(visible.count("│"), 2)

    def test_shuffle_on_shows_icon(self):
        """When shuffle is on, shuffle icon should be visible."""
        tpc.s.state.shuffle = "true"
        result = tpc.artist_row()
        visible = strip_visible(result)
        # Should show shuffle icon
        self.assertIn("🔀", visible)

    def test_shuffle_off_no_icon(self):
        """When shuffle is off, shuffle icon should be hidden."""
        tpc.s.state.shuffle = "false"
        result = tpc.artist_row()
        visible = strip_visible(result)
        # Should NOT show shuffle icon when OFF
        self.assertNotIn("🔀", visible)
        # But should still show "shuf" text
        self.assertIn("shuf", visible)

    def test_loop_track_shows_icon(self):
        """When loop is Track, loop track icon should be visible."""
        tpc.s.state.loop = "Track"
        result = tpc.artist_row()
        visible = strip_visible(result)
        # Should show loop-track icon
        self.assertIn("🔂", visible)

    def test_loop_playlist_shows_icon(self):
        """When loop is Playlist, loop playlist icon should be visible."""
        tpc.s.state.loop = "Playlist"
        result = tpc.artist_row()
        visible = strip_visible(result)
        # Should show loop-playlist icon
        self.assertIn("🔁", visible)

    def test_loop_none_no_icon(self):
        """When loop is None, loop icon should be hidden."""
        tpc.s.state.loop = "None"
        result = tpc.artist_row()
        visible = strip_visible(result)
        # Should NOT show loop icon when OFF
        self.assertNotIn("🔂", visible)
        self.assertNotIn("🔁", visible)
        # But should still show "loop" text
        self.assertIn("loop", visible)

    def test_shuffle_on_with_loop_track(self):
        """When both shuffle on and loop Track, both icons should show."""
        tpc.s.state.shuffle = "true"
        tpc.s.state.loop = "Track"
        result = tpc.artist_row()
        visible = strip_visible(result)
        self.assertIn("🔀", visible)
        self.assertIn("🔂", visible)

    def test_shuffle_text_shown_when_on(self):
        """When shuffle is on, 'shuf' text should be visible."""
        tpc.s.state.shuffle = "true"
        result = tpc.artist_row()
        visible = strip_visible(result)
        self.assertIn("shuf", visible)

    def test_loop_text_shown_when_on(self):
        """When loop is on, 'loop' text should be visible."""
        tpc.s.state.loop = "Playlist"
        result = tpc.artist_row()
        visible = strip_visible(result)
        self.assertIn("loop", visible)

    def test_artist_row_width(self):
        """Artist row should have correct width (72 visible chars)."""
        result = tpc.artist_row()
        visible = strip_visible(result)
        self.assertEqual(tpc.visible_width(visible), 72,
            f"Artist row should be 72 visible chars: {repr(visible)}")

    def test_both_off_shows_both_no_icons(self):
        """When both shuffle and loop are off, both icons hidden, text shown."""
        tpc.s.state.shuffle = "false"
        tpc.s.state.loop = "None"
        result = tpc.artist_row()
        visible = strip_visible(result)
        self.assertIn("Test Artist", visible)
        # Icons should NOT be shown when OFF
        self.assertNotIn("🔀", visible)
        self.assertNotIn("🔂", visible)
        self.assertNotIn("🔁", visible)
        # Text should still be shown
        self.assertIn("shuf", visible)
        self.assertIn("loop", visible)


class TestArtistRowKeyStyling(unittest.TestCase):
    """Test that shuffle/loop show key hints."""

    def setUp(self):
        self._orig = tpc.s.state
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.artist = "Test Artist"
        tpc.s.state.shuffle = "true"
        tpc.s.state.loop = "Track"

    def tearDown(self):
        tpc.s.state = self._orig

    def test_shuffle_s_key_hinted(self):
        """The 's' in shuffle should be highlighted (key hint style)."""
        result = tpc.artist_row()
        # Should have KEY_HINT color applied to 's'
        self.assertIn(tpc.Theme.KEY_HINT, result)

    def test_artist_row_still_shows_label(self):
        """Artist row should still show 'Artist:' label."""
        result = tpc.artist_row()
        visible = strip_visible(result)
        self.assertIn("Artist:", visible)


class TestHandleKeyOptimisticShuffleLoop(unittest.TestCase):
    """Test optimistic updates for shuffle and loop in handle_key."""

    def setUp(self):
        self._orig_state = tpc.s.state
        self._orig_last_cmd = tpc.s.last_command_time
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.shuffle = "false"
        tpc.s.state.loop = "None"
        tpc.s.last_command_time = 0

    def tearDown(self):
        tpc.s.state = self._orig_state
        tpc.s.last_command_time = self._orig_last_cmd

    @patch.object(tpc, "run_playerctl_async")
    def test_shuffle_toggle_optimistic(self, mock_run):
        """Pressing 's' should optimistically toggle shuffle."""
        # Start with shuffle off
        tpc.s.state.shuffle = "false"

        tpc.handle_key("s")

        # State should toggle
        self.assertEqual(tpc.s.state.shuffle, "true")
        mock_run.assert_called_with("shuffle", "Toggle")

    @patch.object(tpc, "run_playerctl_async")
    def test_shuffle_off_optimistic(self, mock_run):
        """Pressing 's' when shuffle is on should turn it off."""
        tpc.s.state.shuffle = "true"

        tpc.handle_key("s")

        self.assertEqual(tpc.s.state.shuffle, "false")
        mock_run.assert_called_with("shuffle", "Toggle")

    @patch.object(tpc, "run_playerctl_async")
    def test_loop_cycle_optimistic(self, mock_run):
        """Pressing 'l' should cycle through loop states."""
        # Start with loop off
        tpc.s.state.loop = "None"

        tpc.handle_key("l")

        self.assertEqual(tpc.s.state.loop, "Track")
        mock_run.assert_called_with("loop", "Track")

    @patch.object(tpc, "run_playerctl_async")
    def test_loop_cycle_track_to_playlist(self, mock_run):
        """Pressing 'l' when loop is Track should cycle to Playlist."""
        tpc.s.state.loop = "Track"

        tpc.handle_key("l")

        self.assertEqual(tpc.s.state.loop, "Playlist")
        mock_run.assert_called_with("loop", "Playlist")

    @patch.object(tpc, "run_playerctl_async")
    def test_loop_cycle_playlist_to_none(self, mock_run):
        """Pressing 'l' when loop is Playlist should cycle to None."""
        tpc.s.state.loop = "Playlist"

        tpc.handle_key("l")

        self.assertEqual(tpc.s.state.loop, "None")
        mock_run.assert_called_with("loop", "None")


class TestMetadataLoopShuffleParsing(unittest.TestCase):
    """Test that loop and shuffle are correctly parsed from metadata."""

    def setUp(self):
        self._orig = tpc.s.state
        tpc.s.state = tpc.PlayerState()

    def tearDown(self):
        tpc.s.state = self._orig

    def test_parse_shuffle_on(self):
        """parse_metadata should parse shuffle 'true'."""
        raw = "\n@37@true"
        result = tpc.parse_metadata(raw)
        self.assertEqual(result.get("shuffle"), "true")

    def test_parse_shuffle_off(self):
        """parse_metadata should parse shuffle 'false'."""
        raw = "\n@37@false"
        result = tpc.parse_metadata(raw)
        self.assertEqual(result.get("shuffle"), "false")

    def test_parse_loop_track(self):
        """parse_metadata should parse loop 'Track'."""
        raw = "\n@36@Track"
        result = tpc.parse_metadata(raw)
        self.assertEqual(result.get("loop"), "Track")

    def test_parse_loop_playlist(self):
        """parse_metadata should parse loop 'Playlist'."""
        raw = "\n@36@Playlist"
        result = tpc.parse_metadata(raw)
        self.assertEqual(result.get("loop"), "Playlist")

    def test_parse_loop_none(self):
        """parse_metadata should parse loop 'None'."""
        raw = "\n@36@None"
        result = tpc.parse_metadata(raw)
        self.assertEqual(result.get("loop"), "None")


if __name__ == "__main__":
    unittest.main(verbosity=2)
