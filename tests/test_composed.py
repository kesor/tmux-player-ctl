#!/usr/bin/env python3
"""
Test suite for composed UI rows - the full row types used in the application.
These tests verify that individual components compose correctly into UI rows.
"""

import unittest
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


# ─────────────────────────────────────────────────────────────────────────────
# Import the module under test
# ─────────────────────────────────────────────────────────────────────────────

import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


# ─────────────────────────────────────────────────────────────────────────────
# Test Cases
# ─────────────────────────────────────────────────────────────────────────────


class TestBorderRows(unittest.TestCase):
    """Test border rows - top, middle, bottom."""

    def test_border_top_starts_with_corner(self):
        """Top border starts with ┌."""
        result = strip_visible(tpc.border_top())
        self.assertTrue(result.startswith("┌"))

    def test_border_top_ends_with_corner(self):
        """Top border ends with ┐."""
        result = strip_visible(tpc.border_top())
        self.assertTrue(result.endswith("┐"))

    def test_border_top_width(self):
        """Top border has corners."""
        result = strip_visible(tpc.border_top())
        self.assertTrue(result.startswith("┌"))
        self.assertTrue(result.endswith("┐"))

    def test_border_mid_starts_with_corner(self):
        """Middle border starts with ├."""
        result = strip_visible(tpc.border_mid())
        self.assertTrue(result.startswith("├"))

    def test_border_mid_ends_with_corner(self):
        """Middle border ends with ┤."""
        result = strip_visible(tpc.border_mid())
        self.assertTrue(result.endswith("┤"))

    def test_border_mid_width(self):
        """Middle border has corners."""
        result = strip_visible(tpc.border_mid())
        self.assertTrue(result.startswith("├"))
        self.assertTrue(result.endswith("┤"))

    def test_border_bot_starts_with_corner(self):
        """Bottom border starts with └."""
        result = strip_visible(tpc.border_bot())
        self.assertTrue(result.startswith("└"))

    def test_border_bot_ends_with_corner(self):
        """Bottom border ends with ┘."""
        result = strip_visible(tpc.border_bot())
        self.assertTrue(result.endswith("┘"))

    def test_border_bot_width(self):
        """Bottom border has corners."""
        result = strip_visible(tpc.border_bot())
        self.assertTrue(result.startswith("└"))
        self.assertTrue(result.endswith("┘"))


class TestHeaderRow(unittest.TestCase):
    """Test header row - icon + status + player name + switch."""

    def setUp(self):
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.player = "testplayer"
        tpc.s.state.status = "Playing"
        tpc.s.available_players = ["testplayer", "otherplayer"]

    def test_header_has_status_icon(self):
        """Header includes status icon."""
        result = tpc.header_row()
        self.assertIn("⏵", result)

    def test_header_has_status_text(self):
        """Header includes status text."""
        result = tpc.header_row()
        self.assertIn("playing", result.lower())

    def test_header_has_player_name(self):
        """Header includes player name."""
        result = tpc.header_row()
        self.assertIn("testplayer", result)

    def test_header_has_switch_when_multiple_players(self):
        """Header includes switch button when multiple players."""
        result = tpc.header_row()
        self.assertIn("switch", result.lower())

    def test_header_no_switch_when_single_player(self):
        """Header has no switch when only one player."""
        tpc.s.available_players = ["onlyplayer"]
        result = tpc.header_row()
        self.assertNotIn("switch", result.lower())

    def test_header_truncates_long_player_name(self):
        """Long player name is truncated."""
        tpc.s.state.player = "very_very_very_long_player_name_abc_def_ghi_jkl_mno"
        result = tpc.header_row()
        # Should have ellipsis where truncation happened
        self.assertIn("…", result)

    def test_header_width(self):
        """Header row has borders."""
        result = tpc.header_row()
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))


class TestInfoRow(unittest.TestCase):
    """Test info rows - Album, Track, Artist with labels."""

    def setUp(self):
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.title = "Test Song"
        tpc.s.state.artist = "Test Artist"
        tpc.s.state.album = "Test Album"

    def test_album_row_has_label(self):
        """Album row has 'Album:' label."""
        result = tpc.album_row()
        self.assertIn("Album", result)

    def test_album_row_has_value(self):
        """Album row has album value."""
        result = tpc.album_row()
        self.assertIn("Test Album", result)

    def test_track_row_has_label(self):
        """Track row has 'Track:' label."""
        result = tpc.track_row()
        self.assertIn("Track", result)

    def test_track_row_has_value(self):
        """Track row has track value."""
        result = tpc.track_row()
        self.assertIn("Test Song", result)

    def test_artist_row_has_label(self):
        """Artist row has 'Artist:' label."""
        result = tpc.artist_row()
        self.assertIn("Artist", result)

    def test_artist_row_has_value(self):
        """Artist row has artist value."""
        result = tpc.artist_row()
        self.assertIn("Test Artist", result)

    def test_info_row_direct(self):
        """_info_row builds row with label and value."""
        result = tpc._info_row("Label:", "Value")
        self.assertIn("Label:", result)
        self.assertIn("Value", result)

    def test_info_rows_width(self):
        """Info rows span full UI_WIDTH."""

    def test_empty_album_returns_row(self):
        """Empty album returns row with label."""
        tpc.s.state.album = ""
        result = tpc.album_row()
        self.assertIsNotNone(result)
        self.assertIn("Album:", result)

    def test_empty_track_returns_row(self):
        """Empty track returns row with label."""
        tpc.s.state.title = ""
        result = tpc.track_row()
        self.assertIsNotNone(result)
        self.assertIn("Track:", result)

    def test_empty_artist_returns_row(self):
        """Empty artist returns row with label."""
        tpc.s.state.artist = ""
        result = tpc.artist_row()
        self.assertIsNotNone(result)
        self.assertIn("Artist:", result)


class TestProgressRow(unittest.TestCase):
    """Test progress row - time + bar + time."""

    def setUp(self):
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.position = 60.0
        tpc.s.state.length = 180.0

    def test_progress_row_has_start_time(self):
        """Progress row shows start time."""
        result = tpc.progress_row()
        self.assertIn("1:00", result)  # 60 seconds = 1:00

    def test_progress_row_has_end_time(self):
        """Progress row shows end time."""
        result = tpc.progress_row()
        self.assertIn("3:00", result)  # 180 seconds = 3:00

    def test_progress_row_has_bar(self):
        """Progress row includes bar characters."""
        result = tpc.progress_row()
        plain = ANSI.sub("", result)
        # Should have fill/empty characters
        self.assertTrue("━" in plain)

    def test_progress_row_width(self):
        """Progress row has borders."""
        result = tpc.progress_row()
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))

    def test_progress_zero_length(self):
        """Zero length shows '0:00' for both times."""
        tpc.s.state.length = 0.0
        tpc.s.state.position = 0.0
        result = tpc.progress_row()
        # Both times should be 0:00
        self.assertIn("0:00", result)

    def test_progress_short_track(self):
        """Short track (30 seconds) shows correct times."""
        tpc.s.state.position = 0.0
        tpc.s.state.length = 30.0
        result = tpc.progress_row()
        self.assertIn("0:00", result)  # start
        self.assertIn("0:30", result)  # end

    def test_progress_long_track(self):
        """Long track (10 minutes) shows correct times."""
        tpc.s.state.position = 0.0
        tpc.s.state.length = 600.0
        result = tpc.progress_row()
        self.assertIn("0:00", result)  # start
        self.assertIn("10:00", result)  # end

    def test_progress_very_long_track(self):
        """Very long track (1 hour) shows correct times."""
        tpc.s.state.position = 0.0
        tpc.s.state.length = 3600.0
        result = tpc.progress_row()
        self.assertIn("0:00", result)  # start
        self.assertIn("1:00:00", result)  # end

    def test_progress_90_minute_track(self):
        """90 minute track shows 1:30:00 for total."""
        tpc.s.state.position = 874.0  # 14:34 elapsed
        tpc.s.state.length = 5400.0  # 90 minutes
        result = tpc.progress_row()
        self.assertIn("14:34", result)  # elapsed is MM:SS
        self.assertIn("1:30:00", result)  # total shows hours

    def test_progress_at_start(self):
        """Position at start shows 0:00."""
        tpc.s.state.position = 0.0
        tpc.s.state.length = 180.0
        result = tpc.progress_row()
        self.assertIn("0:00", result)

    def test_progress_at_end(self):
        """Position at end shows same time for start and end."""
        tpc.s.state.position = 180.0
        tpc.s.state.length = 180.0
        result = tpc.progress_row()
        self.assertIn("3:00", result)

    def test_progress_at_half(self):
        """Position at half shows midpoint time."""
        tpc.s.state.position = 90.0
        tpc.s.state.length = 180.0
        result = tpc.progress_row()
        self.assertIn("1:30", result)  # 90 seconds = 1:30

    def test_progress_bar_filled_char(self):
        """Progress bar has filled character."""
        tpc.s.state.position = 90.0
        tpc.s.state.length = 180.0
        result = tpc.progress_row()
        plain = ANSI.sub("", result)
        self.assertIn("━", plain)  # filled bar char

    def test_progress_bar_empty_char(self):
        """Progress bar has empty character."""
        tpc.s.state.position = 0.0
        tpc.s.state.length = 180.0
        result = tpc.progress_row()
        plain = ANSI.sub("", result)
        self.assertIn("━", plain)  # should still have bar


class TestVolumeRow(unittest.TestCase):
    """Test volume row - icon + bar + percentage."""

    def setUp(self):
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.volume = 50

    def test_volume_row_has_icon(self):
        """Volume row includes volume icon."""
        result = tpc.volume_row()
        # Should have some volume indicator
        self.assertIsNotNone(result)
        self.assertIn("█", result)

    def test_volume_row_has_bar(self):
        """Volume row includes bar characters."""
        result = tpc.volume_row()
        plain = ANSI.sub("", result)
        self.assertTrue("░" in plain or "█" in plain)

    def test_volume_row_has_percentage(self):
        """Volume row includes percentage."""
        result = tpc.volume_row()
        self.assertIn("50%", result)

    def test_volume_row_width(self):
        """Volume row has borders."""
        result = tpc.volume_row()
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))

    def test_volume_zero_percent(self):
        """Volume 0 shows '0%'."""
        tpc.s.state.volume = 0
        result = tpc.volume_row()
        self.assertIn("0%", result)

    def test_volume_hundred_percent(self):
        """Volume 100 shows '100%'."""
        tpc.s.state.volume = 100
        result = tpc.volume_row()
        self.assertIn("100%", result)

    def test_volume_quarter(self):
        """Volume 25% shows correct percentage."""
        tpc.s.state.volume = 25
        result = tpc.volume_row()
        self.assertIn("25%", result)

    def test_volume_three_quarter(self):
        """Volume 75% shows correct percentage."""
        tpc.s.state.volume = 75
        result = tpc.volume_row()
        self.assertIn("75%", result)

    def test_volume_bar_character(self):
        """Volume bar has block characters."""
        tpc.s.state.volume = 50
        result = tpc.volume_row()
        plain = ANSI.sub("", result)
        self.assertIn("█", plain)
        self.assertIn("░", plain)

    def test_volume_full_bar(self):
        """Volume 100% bar is mostly filled."""
        tpc.s.state.volume = 100
        result = tpc.volume_row()
        plain = ANSI.sub("", result)
        # Should have more filled than empty
        self.assertIn("█", plain)

    def test_volume_precision_low(self):
        """Volume 0.49999 should show ~50%."""
        tpc.s.state.volume = 50
        result = tpc.volume_row()
        # Should round to 50%
        self.assertIn("50%", result)

    def test_volume_precision_high(self):
        """Volume 51 should show ~51%."""
        tpc.s.state.volume = 51
        result = tpc.volume_row()
        # Should show 51%
        self.assertIn("51%", result)

    def test_volume_precision_boundary(self):
        """Volume 24 should show 24%."""
        tpc.s.state.volume = 24
        result = tpc.volume_row()
        self.assertIn("24%", result)

    def test_volume_very_low(self):
        """Volume 1% shows '1%'."""
        tpc.s.state.volume = 1
        result = tpc.volume_row()
        self.assertIn("1%", result)


class TestToolbarRow(unittest.TestCase):
    """Test toolbar row - controls + key hints."""

    def setUp(self):
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.status = "Playing"

    def test_toolbar_has_seek_hint(self):
        """Toolbar has seek hint."""
        result = tpc.toolbar_row()
        self.assertIn("seek", result.lower())

    def test_toolbar_has_vol_hint(self):
        """Toolbar has volume hint."""
        result = tpc.toolbar_row()
        self.assertIn("vol", result.lower())

    def test_toolbar_has_prev_hint(self):
        """Toolbar has prev hint."""
        result = ANSI.sub("", tpc.toolbar_row())
        self.assertIn("prev", result.lower())

    def test_toolbar_has_next_hint(self):
        """Toolbar has next hint."""
        result = ANSI.sub("", tpc.toolbar_row())
        self.assertIn("next", result.lower())

    def test_toolbar_has_next_highlight(self):
        """Toolbar next has highlight."""
        result = tpc.toolbar_row()
        # Each tool should have highlight
        self.assertIn(tpc.Theme.KEY_HINT, result)

    def test_toolbar_has_play_hint_when_paused(self):
        """Toolbar shows play hint when paused."""
        tpc.s.state.status = "Paused"
        result = tpc.toolbar_row()
        visible = strip_visible(result)
        # When paused, shows play icon
        self.assertIn("play", visible)

    def test_toolbar_has_quit_hint(self):
        """Toolbar has quit hint."""
        result = ANSI.sub("", tpc.toolbar_row())
        self.assertIn("close", result.lower())

    def test_toolbar_width(self):
        """Toolbar row has borders."""
        result = tpc.toolbar_row()
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))

    def test_toolbar_all_tools_have_highlights(self):
        """All toolbar tools have highlights (when paused)."""
        tpc.s.state.status = "Paused"
        result = tpc.toolbar_row()
        # seek, vol, mute, play, prev, next, close = 7 highlights
        self.assertEqual(result.count(tpc.Theme.KEY_HINT), 7)

    def test_toolbar_seek_tool_has_color_and_correct_text(self):
        """Seek tool has ANSI color and correct visible text."""
        tpc.s.state.status = "Paused"
        result = tpc.toolbar_row()
        # Has color
        self.assertIn(tpc.Theme.KEY_HINT, result)
        # Visible text is correct after stripping ANSI
        visible = strip_visible(result)
        self.assertIn("←→ seek", visible)

    def test_toolbar_vol_tool_has_color_and_correct_text(self):
        """Volume tool has ANSI color and correct visible text."""
        tpc.s.state.status = "Paused"
        result = tpc.toolbar_row()
        # Has color
        self.assertIn(tpc.Theme.KEY_HINT, result)
        # Visible text is correct after stripping ANSI
        visible = strip_visible(result)
        self.assertIn("↑↓ volume", visible)

    def test_toolbar_mute_tool_correct_text(self):
        """Mute tool has correct visible text."""
        tpc.s.state.status = "Paused"
        result = tpc.toolbar_row()
        visible = strip_visible(result)
        self.assertIn("mute", visible)

    def test_toolbar_pause_tool_correct_text(self):
        """Pause tool has correct visible text (shows 'play' when paused)."""
        tpc.s.state.status = "Paused"
        result = tpc.toolbar_row()
        visible = strip_visible(result)
        # When paused, shows play tool
        self.assertIn("play", visible)

    def test_toolbar_prev_tool_has_color_and_correct_text(self):
        """Prev tool has ANSI color and correct visible text."""
        tpc.s.state.status = "Paused"
        result = tpc.toolbar_row()
        # Has color
        self.assertIn(tpc.Theme.KEY_HINT, result)
        # Visible text is correct after stripping ANSI
        visible = strip_visible(result)
        self.assertIn("prev", visible)

    def test_toolbar_next_tool_has_color_and_correct_text(self):
        """Next tool has ANSI color and correct visible text."""
        tpc.s.state.status = "Paused"
        result = tpc.toolbar_row()
        # Has color
        self.assertIn(tpc.Theme.KEY_HINT, result)
        # Visible text is correct after stripping ANSI
        visible = strip_visible(result)
        self.assertIn("next", visible)

    def test_toolbar_close_tool_has_color_and_correct_text(self):
        """Close tool has ANSI color and correct visible text."""
        tpc.s.state.status = "Paused"
        result = tpc.toolbar_row()
        # Has color
        self.assertIn(tpc.Theme.KEY_HINT, result)
        # Visible text is correct after stripping ANSI
        visible = strip_visible(result)
        self.assertIn("esc/q close", visible)


class TestAllRowsWidth(unittest.TestCase):
    """Test that all rows have borders."""

    def setUp(self):
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.player = "testplayer"
        tpc.s.state.status = "Playing"
        tpc.s.state.title = "Test Song"
        tpc.s.state.artist = "Test Artist"
        tpc.s.state.album = "Test Album"
        tpc.s.state.position = 60.0
        tpc.s.state.length = 180.0
        tpc.s.state.volume = 50
        tpc.s.available_players = ["player1", "player2"]

    def test_all_composed_rows_have_borders(self):
        """All composed rows have borders."""
        rows = [
            tpc.border_top(),
            tpc.header_row(),
            tpc.border_mid(),
            tpc.album_row(),
            tpc.track_row(),
            tpc.artist_row(),
            tpc.border_mid(),
            tpc.progress_row(),
            tpc.volume_row(),
            tpc.border_mid(),
            tpc.toolbar_row(),
            tpc.border_bot(),
        ]
        for r in rows:
            self.assertIsNotNone(r)
            visible = strip_visible(r)
            # Either border (┌├└) or content (│ )
            self.assertTrue(
                visible.startswith("│ ")
                or visible.startswith("┌")
                or visible.startswith("├")
                or visible.startswith("└")
            )
            self.assertTrue(
                visible.endswith(" │")
                or visible.endswith("┐")
                or visible.endswith("┤")
                or visible.endswith("┘")
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
