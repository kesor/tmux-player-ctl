#!/usr/bin/env python3
"""
Test suite for UI components: truncate(), row(), overlay(), icon(), colorize(), parse_metadata().
"""

import unittest
import re

ANSI = re.compile(r'\x1b\[[0-9;]*m')

def strip_visible(text):
    """Remove ANSI codes and VS15/VS16."""
    return ANSI.sub('', text).replace('\ufe0e', '').replace('\ufe0f', '').replace('\u200b', '')

# ─────────────────────────────────────────────────────────────────────────────
# Test Fixtures
# ─────────────────────────────────────────────────────────────────────────────

FIXTURES = {
    "playing": {
        "metadata": "spotify\u2420Playing\u2420Test Song\u2420Test Artist\u2420Test Album\u242060000\u2420180000\u24200.75\u2420None\u2420false",
        "status": "Playing",
        "position": "60000",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Import the module under test
# ─────────────────────────────────────────────────────────────────────────────

import importlib.util
spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


# ─────────────────────────────────────────────────────────────────────────────
# Test Cases
# ─────────────────────────────────────────────────────────────────────────────

class TestTruncate(unittest.TestCase):
    """Test truncate() - fit content into a width slot."""

    def test_truncate_short_content(self):
        result = tpc.truncate("Hi", 10)
        self.assertEqual(result, "Hi")

    def test_truncate_exact_width(self):
        result = tpc.truncate("Hello", 5)
        self.assertEqual(result, "Hello")

    def test_truncate_long_content(self):
        result = tpc.truncate("Hello World", 8)
        self.assertTrue(result.endswith("…"))
        self.assertIn("…", result)

    def test_truncate_shorter_than_width(self):
        result = tpc.truncate("Hello", 4)
        self.assertTrue(result.endswith("…"))

    def test_truncate_returns_plain_text(self):
        result = tpc.truncate("Hello World", 20)
        self.assertIsNone(re.search(r'\x1b', result))

    def test_truncate_empty_string(self):
        result = tpc.truncate("", 10)
        self.assertEqual(result, "")

    def test_truncate_width_zero(self):
        result = tpc.truncate("Hello", 0)
        # Zero width means return ellipsis only
        self.assertEqual(result, "…")

    def test_truncate_width_one(self):
        result = tpc.truncate("Hello", 1)
        self.assertEqual(result, "…")

    def test_truncate_one_char_shorter(self):
        result = tpc.truncate("abcd", 5)
        # No truncation needed
        self.assertEqual(result, "abcd")

    def test_truncate_one_char_over(self):
        result = tpc.truncate("abcde", 4)
        # Should be truncated and end with ellipsis
        self.assertTrue(result.endswith("…"))


class TestRow(unittest.TestCase):
    """Test row() - compose content slots into a bordered row."""

    def test_row_one_slot(self):
        result = tpc.row(("Title", 20, '^'))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))
        self.assertIn("Title", result)

    def test_row_two_slots(self):
        result = tpc.row(("hi", 2, '<'), ("bye", 3, '>'))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))
        self.assertIn("hi", result)
        self.assertIn("bye", result)
        self.assertIn(" ", result)

    def test_row_three_slots(self):
        result = tpc.row(("L", 1, '<'), ("C", 1, '^'), ("R", 1, '>'))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))
        self.assertIn("L", result)
        self.assertIn("C", result)
        self.assertIn("R", result)

    def test_row_none_skipped(self):
        result = tpc.row(("L", 1, '<'), None, ("R", 1, '>'))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))
        self.assertIn("L", result)
        self.assertIn("R", result)

    def test_row_preserves_ansi_colors(self):
        colored = "\x1b[92mPlaying\x1b[0m"
        result = tpc.row((colored, 7, '<'), None, ("1:30", 5, '>'))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))
        self.assertIn("\x1b[92m", result)

    def test_row_with_icon_overlay(self):
        icon_overlay = tpc.overlay("▶")
        result = tpc.row((icon_overlay, 4, '<'), ("Title", 10, '^'))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertIn("▶", result)
        self.assertIn("Title", result)

    def test_row_with_volume_bar_content(self):
        bar = tpc.volume_bar(50, 10)
        result = tpc.row((bar, 10, '^'))
        self.assertIn("█", result)
        self.assertIn("░", result)

    def test_row_with_progress_bar_content(self):
        bar = tpc.progress_bar(30.0, 100.0, 10)
        result = tpc.row((bar, 10, '^'))
        self.assertTrue("━" in result or "█" in result)

    def test_row_mixed_content(self):
        icon = tpc.colorize("▶", "\x1b[92m")
        text = "Playing"
        pct = tpc.colorize("75%", "\x1b[97m")
        result = tpc.row((icon, 1, '<'), (text, 10, '<'), (pct, 5, '>'))
        self.assertIn("▶", result)
        self.assertIn("Playing", result)
        self.assertIn("75%", result)

    def test_row_with_icon_overlay_content(self):
        icon = tpc.colorize("▶", "\x1b[92m")
        text = "Playing"
        pct = tpc.colorize("75%", "\x1b[97m")
        result = tpc.row((icon, 1, '<'), (text, 10, '<'), (pct, 5, '>'))
        self.assertIn("▶", result)
        self.assertIn("Playing", result)
        self.assertIn("75%", result)

    def test_row_all_slots_total_width(self):
        icon = tpc.icon("play")
        result = tpc.row((icon, 4, '<'), ("Test Title", 20, '^'))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))
        self.assertIn("⏵", result)
        self.assertIn("Test Title", result)



    def test_volume_bar_zero_fills_none(self):
        """Volume 0 returns all empty blocks."""
        result = tpc.volume_bar(0, 10)
        # Should be 10 empty blocks (no filled)
        self.assertNotIn("█", result)
        self.assertIn("░", result)

    def test_volume_bar_full_fills_all(self):
        """Volume 100 returns all filled blocks."""
        result = tpc.volume_bar(100, 10)
        # Should be 10 filled blocks
        filled = result.count("█")
        self.assertEqual(filled, 10)

    def test_volume_bar_half_fills_half(self):
        """Volume 50 returns half filled, half empty."""
        result = tpc.volume_bar(50, 10)
        filled = result.count("█")
        empty = result.count("░")
        self.assertEqual(filled + empty, 10)

    def test_volume_bar_clamped_at_max(self):
        """Volume > 100 clamped to 100."""
        result = tpc.volume_bar(150, 10)
        filled = result.count("█")
        self.assertEqual(filled, 10)

    def test_volume_bar_color_muted(self):
        """Volume 0 uses VOL_MUTED color."""
        result = tpc.volume_bar(0, 10)
        self.assertIn(tpc.Theme.VOL_MUTED, result)

    def test_volume_bar_color_low(self):
        """Volume 1-33 uses VOL_LOW color."""
        result = tpc.volume_bar(20, 10)
        self.assertIn(tpc.Theme.VOL_LOW, result)

    def test_volume_bar_color_med(self):
        """Volume 34-66 uses VOL_MED color."""
        result = tpc.volume_bar(50, 10)
        self.assertIn(tpc.Theme.VOL_MED, result)

    def test_volume_bar_color_high(self):
        """Volume 67-100 uses VOL_HIGH color."""
        result = tpc.volume_bar(80, 10)
        self.assertIn(tpc.Theme.VOL_HIGH, result)

    def test_volume_bar_resets_color(self):
        """Volume bar ends with color reset."""
        result = tpc.volume_bar(50, 10)
        self.assertIn("\033[0m", result)


class TestProgressBar(unittest.TestCase):
    """Test progress_bar() - track progress bar."""

    def test_progress_bar_zero_returns_empty(self):
        """Zero progress uses PROGRESS_EMPTY color."""
        result = tpc.progress_bar(0.0, 100.0, 10)
        self.assertIn(tpc.Theme.PROGRESS_EMPTY, result)

    def test_progress_bar_full_returns_filled(self):
        """100% progress uses PROGRESS_FILL color."""
        result = tpc.progress_bar(100.0, 100.0, 10)
        self.assertIn(tpc.Theme.PROGRESS_FILL, result)

    def test_progress_bar_half(self):
        """50% progress has both PROGRESS_FILL and PROGRESS_EMPTY."""
        result = tpc.progress_bar(50.0, 100.0, 10)
        self.assertIn(tpc.Theme.PROGRESS_FILL, result)
        self.assertIn(tpc.Theme.PROGRESS_EMPTY, result)

    def test_progress_bar_preserves_color_codes(self):
        """Progress bar contains ANSI color codes."""
        result = tpc.progress_bar(50.0, 100.0, 10)
        self.assertIsNotNone(re.search(r'\x1b\[[0-9;]+m', result))

    def test_progress_bar_has_reset(self):
        """Progress bar ends with color reset."""
        result = tpc.progress_bar(50.0, 100.0, 10)
        self.assertIn("\033[0m", result)


class TestFormatTime(unittest.TestCase):
    """Test format_time() - seconds to MM:SS formatting."""

    def test_format_time_zero(self):
        result = tpc.format_time(0.0)
        self.assertEqual(result, "0:00")

    def test_format_time_seconds_only(self):
        result = tpc.format_time(45.0)
        self.assertEqual(result, "0:45")

    def test_format_time_one_minute(self):
        result = tpc.format_time(60.0)
        self.assertEqual(result, "1:00")

    def test_format_time_minutes_and_seconds(self):
        result = tpc.format_time(125.0)
        self.assertEqual(result, "2:05")

    def test_format_time_negative_returns_zero(self):
        result = tpc.format_time(-10.0)
        self.assertEqual(result, "0:00")


class TestOverlay(unittest.TestCase):
    """Test overlay() - fixed-width slot mechanics only."""

    def test_overlay_returns_spaces_back_save_content_restore(self):
        result = tpc.overlay("▶")
        self.assertTrue(result.startswith("  "))  # default width=2
        self.assertIn("\x1b[2D", result)
        self.assertIn("\x1b7", result)
        self.assertIn("▶", result)
        self.assertIn("\x1b[0m", result)
        self.assertIn("\x1b8", result)

    def test_overlay_returns_content_unchanged(self):
        result = tpc.overlay("▶")
        self.assertIn("▶", result)


class TestOverlayIcon(unittest.TestCase):
    """Test overlay() with custom widths."""

    def test_overlay_icon_format(self):
        result = tpc.overlay("▶", 4)
        self.assertTrue(result.startswith("    "))
        self.assertIn("\x1b[4D", result)
        self.assertIn("▶", result)
        self.assertIn("\x1b8", result)

    def test_overlay_icon_custom_width(self):
        result = tpc.overlay("▶", 6)
        self.assertTrue(result.startswith("      "))  # 6 spaces
        self.assertIn("\x1b[6D", result)
        self.assertIn("\x1b8", result)


class TestColorize(unittest.TestCase):
    """Test colorize() - adds ANSI color to content."""

    def test_colorize_wraps_content_with_color(self):
        result = tpc.colorize("hello", "\x1b[92m")
        self.assertEqual(result, "\x1b[92mhello\x1b[0m")


class TestIcon(unittest.TestCase):
    """Test icon() - single function returning fixed-width overlays by name."""

    # VS15 (\uFE0E) forces text presentation, not emoji

    def test_icon_play(self):
        result = tpc.icon("play")
        self.assertIn("\u23F5\uFE0E", result)  # ⏵
        self.assertTrue(result.startswith("  "))

    def test_icon_pause(self):
        result = tpc.icon("pause")
        self.assertIn("⏸\uFE0E", result)
        self.assertTrue(result.startswith("  "))

    def test_icon_stop(self):
        result = tpc.icon("stop")
        self.assertIn("■\uFE0E", result)
        self.assertTrue(result.startswith("  "))

    def test_icon_play_pause(self):
        result = tpc.icon("play-pause")
        self.assertIn("⏯\uFE0E", result)
        self.assertTrue(result.startswith("  "))

    def test_icon_prev(self):
        result = tpc.icon("prev")
        self.assertIn("◀\uFE0E", result)
        self.assertTrue(result.startswith("  "))

    def test_icon_seek_left(self):
        result = tpc.icon("seek-left")
        self.assertIn("⏪\uFE0E", result)
        self.assertTrue(result.startswith("  "))

    def test_icon_seek_right(self):
        result = tpc.icon("seek-right")
        self.assertIn("⏩\uFE0E", result)
        self.assertTrue(result.startswith("  "))

    def test_icon_next(self):
        result = tpc.icon("next")
        self.assertIn("⏭\uFE0E", result)
        self.assertTrue(result.startswith("  "))

    def test_icon_skip_start(self):
        result = tpc.icon("skip-start")
        self.assertIn("⏮\uFE0E", result)
        self.assertTrue(result.startswith("  "))

    def test_icon_skip_end(self):
        result = tpc.icon("skip-end")
        self.assertIn("⏭\uFE0E", result)
        self.assertTrue(result.startswith("  "))

    def test_icon_eject(self):
        result = tpc.icon("eject")
        self.assertIn("⏏\uFE0E", result)
        self.assertTrue(result.startswith("  "))

    def test_icon_vol_muted(self):
        result = tpc.icon("vol-muted")
        self.assertTrue(result.startswith("  "))
        self.assertIn("\uFE0E", result)

    def test_icon_vol_low(self):
        result = tpc.icon("vol-low")
        self.assertTrue(result.startswith("  "))
        self.assertIn("\uFE0E", result)

    def test_icon_vol_med(self):
        result = tpc.icon("vol-med")
        self.assertTrue(result.startswith("  "))
        self.assertIn("\uFE0E", result)

    def test_icon_vol_high(self):
        result = tpc.icon("vol-high")
        self.assertTrue(result.startswith("  "))
        self.assertIn("\uFE0E", result)

    def test_icon_shuffle(self):
        result = tpc.icon("shuffle")
        self.assertTrue(result.startswith("  "))
        self.assertIn("\uFE0E", result)

    def test_icon_repeat(self):
        result = tpc.icon("repeat")
        self.assertTrue(result.startswith("  "))
        self.assertIn("\uFE0E", result)

    def test_icon_repeat_one(self):
        result = tpc.icon("repeat-one")
        self.assertTrue(result.startswith("  "))
        self.assertIn("\uFE0E", result)

    def test_icon_with_custom_width(self):
        """Icon accepts custom width parameter."""
        result = tpc.icon("play", width=5)
        self.assertTrue(result.startswith("     "))  # 5 spaces
        self.assertIn("\u23F5\uFE0E", result)  # ⏵

    def test_icon_with_width_4(self):
        """Icon with width 4 matches time display width."""
        result = tpc.icon("vol-high", width=4)
        self.assertTrue(result.startswith("    "))  # 4 spaces
        self.assertIn("🔊\uFE0E", result)

    def test_icon_default_width_without_param(self):
        """Icon uses default width when no param provided."""
        result_default = tpc.icon("play")
        result_explicit = tpc.icon("play", width=None)
        self.assertEqual(result_default, result_explicit)





def make_metadata(**kwargs):
    """Create a metadata string with defaults for all fields."""
    fields = {
        "player": "",
        "status": "",
        "title": "",
        "artist": "",
        "album": "",
        "albumArtist": "",
        "trackNumber": "",
        "discNumber": "",
        "genre": "",
        "explicit": "false",
        "subtitle": "",
        "asText": "",
        "composer": "",
        "lyricist": "",
        "conductor": "",
        "performer": "",
        "arranger": "",
        "releaseDate": "",
        "contentCreated": "",
        "musicBrainzTrackId": "",
        "musicBrainzAlbumId": "",
        "musicBrainzArtistIds": "",
        "comment": "",
        "mood": "",
        "url": "",
        "userHomePage": "",
        "useCount": "",
        "autoRating": "",
        "audioBPM": "",
        "language": "",
        "lyrics": "",
        "position": "",
        "length": "",
        "volume": "0.0",
        "loopStatus": "None",
        "loop": "None",
        "shuffle": "false",
        "artUrl": "",
        "trackid": "",
    }
    fields.update(kwargs)
    return "\n".join([
        fields["player"],
        fields["status"],
        fields["title"],
        fields["artist"],
        fields["album"],
        fields["albumArtist"],
        fields["trackNumber"],
        fields["discNumber"],
        fields["genre"],
        fields["explicit"],
        fields["subtitle"],
        fields["asText"],
        fields["composer"],
        fields["lyricist"],
        fields["conductor"],
        fields["performer"],
        fields["arranger"],
        fields["releaseDate"],
        fields["contentCreated"],
        fields["musicBrainzTrackId"],
        fields["musicBrainzAlbumId"],
        fields["musicBrainzArtistIds"],
        fields["comment"],
        fields["mood"],
        fields["url"],
        fields["userHomePage"],
        fields["useCount"],
        fields["autoRating"],
        fields["audioBPM"],
        fields["language"],
        fields["lyrics"],
        fields["position"],
        fields["length"],
        fields["volume"],
        fields["loopStatus"],
        fields["loop"],
        fields["shuffle"],
        fields["artUrl"],
        fields["trackid"],
    ])

class TestMetadataParse(unittest.TestCase):
    """Test parse_metadata() - parse playerctl metadata output."""

    # Format: player␣status␣title␣artist␣album␣position␣length␣volume␣loop␣shuffle
    # position and length are in MICROSECONDS

    
    def test_metadata_parse_valid(self):
        raw = make_metadata(
            player="spotify",
            status="Playing",
            title="Song Title",
            artist="Artist Name",
            album="Album Name",
            position="1000000",
            length="2000000",
            volume="0.75",
            loop="None",
            shuffle="false"
        )
        result = tpc.parse_metadata(raw)

        self.assertEqual(result["player"], "spotify")
        self.assertEqual(result["status"], "Playing")
        self.assertEqual(result["title"], "Song Title")
        self.assertEqual(result["artist"], "Artist Name")
        self.assertEqual(result["album"], "Album Name")
        self.assertEqual(result["position"], 1.0)
        self.assertEqual(result["length"], 2.0)
        self.assertEqual(result["volume"], 75)
        self.assertEqual(result["loop"], "None")
        self.assertEqual(result["shuffle"], "false")

    def test_metadata_parse_empty_fields(self):
        raw = make_metadata(
            player="mpd",
            status="Stopped",
            position="0",
            length="0",
            volume="0.0"
        )
        result = tpc.parse_metadata(raw)

        self.assertEqual(result["player"], "mpd")
        self.assertEqual(result["status"], "Stopped")
        self.assertEqual(result["title"], "")
        self.assertEqual(result["artist"], "")
        self.assertEqual(result["album"], "")

    def test_metadata_parse_empty_string(self):
        raw = ""
        result = tpc.parse_metadata(raw)
        self.assertEqual(result, {})

    def test_metadata_parse_loop_none(self):
        raw = make_metadata(loop="None")
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["loop"], "None")

    def test_metadata_parse_loop_track(self):
        raw = make_metadata(loop="Track")
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["loop"], "Track")

    def test_metadata_parse_loop_playlist(self):
        raw = make_metadata(loop="Playlist")
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["loop"], "Playlist")

    def test_metadata_parse_shuffle_on(self):
        raw = make_metadata(shuffle="On")
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["shuffle"], "On")

    def test_metadata_parse_shuffle_off(self):
        raw = make_metadata(shuffle="Off")
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["shuffle"], "Off")

    def test_metadata_parse_volume_zero(self):
        raw = make_metadata(volume="0.0")
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["volume"], 0)

    def test_metadata_parse_volume_one(self):
        raw = make_metadata(volume="1.0")
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["volume"], 100)

    def test_metadata_parse_position_zero(self):
        raw = make_metadata(position="0", length="1800000")
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["position"], 0.0)

    def test_metadata_parse_length_zero(self):
        raw = make_metadata(position="0", length="0")
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["length"], 0.0)

    def test_metadata_parse_position_in_seconds(self):
        raw = make_metadata(position="8584632", length="231529000")
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["position"], 8.584632)
        self.assertEqual(result["length"], 231.529)

    def test_metadata_parse_paused_status(self):
        raw = make_metadata(status="Paused")
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["status"], "Paused")

    def test_metadata_parse_recording_status(self):
        raw = make_metadata(status="Recording")
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["status"], "Recording")

    def test_metadata_parse_volume_rounding_exact(self):
        for vol_float, expected in [
            (0.0, 0),
            (0.5, 50),
            (1.0, 100),
        ]:
            raw = make_metadata(volume=str(vol_float))
            result = tpc.parse_metadata(raw)
            self.assertEqual(result["volume"], expected, f"{vol_float} -> {expected}")

    def test_metadata_parse_volume_rounding_fractional(self):
        for vol_float, expected in [
            (0.1, 10),
            (0.2, 20),
            (0.3, 30),
            (0.4, 40),
            (0.6, 60),
            (0.7, 70),
            (0.8, 80),
            (0.9, 90),
        ]:
            raw = make_metadata(volume=str(vol_float))
            result = tpc.parse_metadata(raw)
            self.assertEqual(result["volume"], expected, f"{vol_float} -> {expected}")

    def test_metadata_parse_volume_rounding_boundary(self):
        for vol_float, expected in [
            (0.249, 25),
            (0.25, 25),
            (0.251, 25),
            (0.749, 75),
            (0.75, 75),
            (0.751, 75),
        ]:
            raw = make_metadata(volume=str(vol_float))
            result = tpc.parse_metadata(raw)
            self.assertEqual(result["volume"], expected, f"{vol_float} -> {expected}")

    def test_metadata_parse_volume_rounding_clamp(self):
        for vol_float, expected in [
            (-0.1, 0),
            (1.1, 100),
            (0.0, 0),
            (1.0, 100),
        ]:
            raw = make_metadata(volume=str(vol_float))
            result = tpc.parse_metadata(raw)
            self.assertEqual(result["volume"], expected, f"{vol_float} -> {expected}")

class TestLayout(unittest.TestCase):
    """Test layout concerns - positioning and width."""

    def test_row_with_icon_and_text_fits_width(self):
        """Icon overlay + text should fit in row width."""
        icon = tpc.overlay("▶")
        text = "Test Song Title"
        result = tpc.row((icon, 4, '<'), (text, 20, '^'))
        # Just check it has borders
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))

    def test_row_with_progress_bar_fits_width(self):
        """Progress bar should fit in row width."""
        bar = tpc.progress_bar(30.0, 100.0, 40)
        result = tpc.row((bar, 40, '^'))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))

    def test_row_with_volume_bar_fits_width(self):
        """Volume bar should fit in row width."""
        bar = tpc.volume_bar(50, 40)
        result = tpc.row((bar, 40, '^'))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))

    def test_row_all_slots_total_width(self):
        """Row contains icon and title content."""
        icon = tpc.overlay("▶")
        result = tpc.row((icon, 4, '<'), ("Test Title", 10, '^'))

        self.assertIn("▶", result)
        self.assertIn("Test Title", result)


class TestRenderUI(unittest.TestCase):
    """Test render_ui() - dynamic row building."""

    def setUp(self):
        # Save original state
        self._orig_players = tpc.available_players
        self._orig_state = tpc.state
        # Create fresh state
        tpc.state = tpc.PlayerState()
        tpc.state.player = "spotify"
        tpc.state.status = "Playing"
        tpc.state.position = 60.0
        tpc.state.length = 180.0
        tpc.state.volume = 75
        tpc.available_players = ["spotify"]

    def tearDown(self):
        tpc.state = self._orig_state
        tpc.available_players = self._orig_players

    def test_render_ui_all_fields_present(self):
        """All metadata fields present - all info rows rendered."""
        tpc.state.title = "Test Song"
        tpc.state.artist = "Test Artist"
        tpc.state.album = "Test Album"
        # Use a StringIO to capture output
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            tpc.render_ui()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        # All info rows should be present
        self.assertIn("Album:", output)
        self.assertIn("Test Album", output)
        self.assertIn("Track:", output)
        self.assertIn("Test Song", output)
        self.assertIn("Artist:", output)
        self.assertIn("Test Artist", output)
        # Borders present
        self.assertIn("┌", output)
        self.assertIn("└", output)
        self.assertIn("├", output)

    def test_render_ui_missing_album(self):
        """Album missing - empty row shown instead."""
        tpc.state.title = "Test Song"
        tpc.state.artist = "Test Artist"
        tpc.state.album = ""
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            tpc.render_ui()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        # Album row present even when empty
        self.assertIn("Album:", output)
        # Track and Artist rows still have labels
        self.assertIn("Track:", output)
        self.assertIn("Artist:", output)

    def test_render_ui_missing_title(self):
        """Title missing - track row still shown with label."""
        tpc.state.title = ""
        tpc.state.artist = "Test Artist"
        tpc.state.album = "Test Album"
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            tpc.render_ui()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        self.assertIn("Track:", output)
        self.assertIn("Album:", output)
        self.assertIn("Artist:", output)

    def test_render_ui_missing_artist(self):
        """Artist missing - artist row still shown with label."""
        tpc.state.title = "Test Song"
        tpc.state.artist = ""
        tpc.state.album = "Test Album"
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            tpc.render_ui()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        self.assertIn("Artist:", output)
        self.assertIn("Album:", output)
        self.assertIn("Track:", output)

    def test_render_ui_empty_row_when_no_album(self):
        """When album is missing, padding row added at end (no Album label)."""
        tpc.state.title = "Test Song"
        tpc.state.artist = "Test Artist"
        tpc.state.album = ""
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            tpc.render_ui()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        # Album row is present even when empty
        self.assertIn("Album:", output)
        # Track and Artist still visible
        self.assertIn("Track:", output)
        self.assertIn("Artist:", output)
        # Has border characters (verifies output)
        self.assertIn("┌", output)
        self.assertIn("└", output)

    def test_render_ui_with_album(self):
        """With album present, all info rows visible."""
        tpc.state.title = "Test Song"
        tpc.state.artist = "Test Artist"
        tpc.state.album = "Test Album"
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            tpc.render_ui()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        # Album visible
        self.assertIn("Album:", output)
        self.assertIn("Track:", output)
        self.assertIn("Artist:", output)

    def test_render_ui_all_missing(self):
        """All metadata missing - all info rows still shown with labels."""
        tpc.state.title = ""
        tpc.state.artist = ""
        tpc.state.album = ""
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            tpc.render_ui()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        # All info rows present even when empty
        self.assertIn("Album:", output)
        self.assertIn("Track:", output)
        self.assertIn("Artist:", output)
        # And has structure
        self.assertIn("┌", output)
        self.assertIn("└", output)
        # And progress/volume
        self.assertIn("spotify", output)
        self.assertIn("seek", output)


class TestThemeResetWithBackground(unittest.TestCase):
    """Test that Theme.RESET includes background when TPCTL_BG is set."""
    
    def test_reset_without_bg(self):
        """Without BG, RESET is just SGR 0."""
        # Reload module without BG
        import importlib
        import importlib.util
        import os
        # Remove BG env var
        old_bg = os.environ.pop('TPCTL_BG', None)
        try:
            spec = importlib.util.spec_from_file_location('tpc2', '../tmux-player-ctl.py')
            tpc2 = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(tpc2)
            # Should be just \033[0m
            self.assertEqual(tpc2.Theme.RESET, '\033[0m')
        finally:
            if old_bg:
                os.environ['TPCTL_BG'] = old_bg
    
    def test_reset_with_bg(self):
        """With BG set, RESET includes background color."""
        import importlib
        import importlib.util
        import os
        os.environ['TPCTL_BG'] = '30;30;50'
        try:
            spec = importlib.util.spec_from_file_location('tpc3', '../tmux-player-ctl.py')
            tpc3 = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(tpc3)
            # Should be \033[0m followed by background
            self.assertEqual(tpc3.Theme.RESET, '\033[0m\033[48;2;30;30;50m')
        finally:
            del os.environ['TPCTL_BG']


if __name__ == "__main__":
    unittest.main(verbosity=2)
