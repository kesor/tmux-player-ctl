#!/usr/bin/env python3
"""
Test suite for UI components: truncate(), row(), icon(), colorize(), parse_metadata().
"""

import unittest
import re

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def strip_visible(text):
    """Remove ANSI codes and VS15/VS16."""
    return (
        ANSI.sub("", text)
        .replace("\ufe0e", "")
        .replace("\ufe0f", "")
        .replace("\u200b", "")
    )


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

import importlib.util  # noqa: E402

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
        self.assertIsNone(re.search(r"\x1b", result))

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
        result = tpc.row(("Title", 20, "^"))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))
        self.assertIn("Title", result)

    def test_row_two_slots(self):
        result = tpc.row(("hi", 2, "<"), ("bye", 3, ">"))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))
        self.assertIn("hi", result)
        self.assertIn("bye", result)
        self.assertIn(" ", result)

    def test_row_three_slots(self):
        result = tpc.row(("L", 1, "<"), ("C", 1, "^"), ("R", 1, ">"))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))
        self.assertIn("L", result)
        self.assertIn("C", result)
        self.assertIn("R", result)

    def test_row_none_skipped(self):
        result = tpc.row(("L", 1, "<"), None, ("R", 1, ">"))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))
        self.assertIn("L", result)
        self.assertIn("R", result)

    def test_row_preserves_ansi_colors(self):
        colored = "\x1b[92mPlaying\x1b[0m"
        result = tpc.row((colored, 7, "<"), None, ("1:30", 5, ">"))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))
        self.assertIn("\x1b[92m", result)

    def test_row_with_icon_and_text(self):
        icon = tpc.icon("playing")
        result = tpc.row((f"{icon:<4}", 4, "<"), (f"{'Title':<10}", 10, "^"))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertIn("⏵", result)
        self.assertIn("Title", result)

    def test_row_with_volume_bar_content(self):
        bar = tpc.volume_bar(50, 10)
        result = tpc.row((bar, 10, "^"))
        self.assertIn("█", result)
        self.assertIn("░", result)

    def test_row_with_progress_bar_content(self):
        bar = tpc.progress_bar(30.0, 100.0, 10)
        result = tpc.row((bar, 10, "^"))
        self.assertTrue("━" in result or "█" in result)

    def test_row_mixed_content(self):
        icon = tpc.colorize("▶", "\x1b[92m")
        text = "Playing"
        pct = tpc.colorize("75%", "\x1b[97m")
        result = tpc.row((icon, 1, "<"), (text, 10, "<"), (pct, 5, ">"))
        self.assertIn("▶", result)
        self.assertIn("Playing", result)
        self.assertIn("75%", result)

    def test_row_with_icon_overlay_content(self):
        icon = tpc.colorize("▶", "\x1b[92m")
        text = "Playing"
        pct = tpc.colorize("75%", "\x1b[97m")
        result = tpc.row((icon, 1, "<"), (text, 10, "<"), (pct, 5, ">"))
        self.assertIn("▶", result)
        self.assertIn("Playing", result)
        self.assertIn("75%", result)

    def test_row_all_slots_total_width(self):
        icon = tpc.icon("playing")
        result = tpc.row((icon, 4, "<"), ("Test Title", 20, "^"))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))
        self.assertIn("⏵", result)
        self.assertIn("Test Title", result)

    def test_volume_bar_zero_shows_empty_blocks(self):
        """Volume 0 returns all empty blocks."""
        result = tpc.volume_bar(0, 10)
        # Should be 10 empty blocks
        self.assertNotIn("█", result)
        self.assertIn("░", result)

    def test_volume_bar_full_fills_all(self):
        """Volume 100 fills all character positions."""
        result = tpc.volume_bar(100, 10)
        # Should be 10 characters (filled blocks or dither chars)
        filled = result.count("█") + result.count("▒") + result.count("▓")
        self.assertEqual(filled, 10)

    def test_volume_bar_half_fills_half(self):
        """Volume 50 fills half the bar."""
        result = tpc.volume_bar(50, 10)
        filled = result.count("█") + result.count("▒") + result.count("▓")
        empty = result.count("░")
        self.assertEqual(filled, 5)
        self.assertEqual(empty, 5)

    def test_volume_bar_clamped_at_max(self):
        """Volume > 100 clamped to full."""
        result = tpc.volume_bar(150, 10)
        filled = result.count("█") + result.count("▒") + result.count("▓")
        self.assertEqual(filled, 10)

    def test_volume_bar_has_green_zone(self):
        """Volume bar in green zone uses VOL_LOW color."""
        result = tpc.volume_bar(30, 10)  # 30% = green zone
        self.assertIn(tpc.Theme.VOL_LOW, result)

    def test_volume_bar_has_yellow_zone(self):
        """Volume bar in yellow zone uses VOL_MED color."""
        result = tpc.volume_bar(60, 10)  # 60% = yellow zone
        self.assertIn(tpc.Theme.VOL_MED, result)

    def test_volume_bar_has_red_zone(self):
        """Volume bar in red zone uses VOL_HIGH color."""
        result = tpc.volume_bar(90, 10)  # 90% = red zone
        self.assertIn(tpc.Theme.VOL_HIGH, result)

    def test_volume_bar_has_empty_section(self):
        """Volume bar has empty blocks after filled section."""
        result = tpc.volume_bar(70, 10)  # 70% filled
        self.assertIn("░", result)  # Has empty blocks

    def test_volume_bar_empty_section_uses_vol_empty(self):
        """Empty section uses VOL_EMPTY theme color for both FG and BG."""
        result = tpc.volume_bar(70, 10)  # 70% filled, 30% empty
        import re
        # Extract VOL_EMPTY RGB value from theme
        vol_empty_rgb = tpc._color_rgb(tpc.Theme.VOL_EMPTY)
        # The empty section should have BG set to VOL_EMPTY
        self.assertIn(f"\033[48;2;{vol_empty_rgb}m", result)

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
        self.assertIsNotNone(re.search(r"\x1b\[[0-9;]+m", result))

    def test_progress_bar_has_reset(self):
        """Progress bar ends with color reset."""
        result = tpc.progress_bar(50.0, 100.0, 10)
        self.assertIn("\033[0m", result)

    def test_progress_bar_beyond_length_returns_full_bar(self):
        """Progress beyond track length should return full bar (not overflow)."""
        # Bug: when seeking beyond track length, bar became 1 char longer
        result = tpc.progress_bar(110.0, 100.0, 10)
        # Should still be exactly 10 characters (not 11)
        visible = ANSI.sub("", result)
        self.assertEqual(len(visible), 10)

    def test_progress_bar_at_length_is_full(self):
        """Progress at 100% should show full bar."""
        result = tpc.progress_bar(100.0, 100.0, 10)
        visible = ANSI.sub("", result)
        self.assertEqual(len(visible), 10)

    def test_progress_bar_slightly_beyond_length(self):
        """Progress slightly beyond track length should still fit."""
        result = tpc.progress_bar(100.1, 100.0, 10)
        visible = ANSI.sub("", result)
        self.assertEqual(len(visible), 10)


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


class TestColorize(unittest.TestCase):
    """Test colorize() - adds ANSI color to content."""

    def test_colorize_wraps_content_with_color(self):
        result = tpc.colorize("hello", "\x1b[92m")
        self.assertEqual(result, "\x1b[92mhello\x1b[0m")


class TestIcon(unittest.TestCase):
    """Test icon() - returns raw symbol from ICONS by name."""

    def test_icon_play(self):
        result = tpc.icon("playing")
        self.assertEqual(result, tpc.ICONS["playing"])

    def test_icon_pause(self):
        result = tpc.icon("paused")
        self.assertEqual(result, tpc.ICONS["paused"])

    def test_icon_stop(self):
        result = tpc.icon("stopped")
        self.assertEqual(result, tpc.ICONS["stopped"])

    def test_icon_play_pause(self):
        result = tpc.icon("play-pause")
        self.assertEqual(result, tpc.ICONS["play-pause"])

    def test_icon_prev(self):
        result = tpc.icon("prev")
        self.assertEqual(result, tpc.ICONS["prev"])

    def test_icon_seek_left(self):
        result = tpc.icon("seek-left")
        self.assertEqual(result, tpc.ICONS["seek-left"])

    def test_icon_seek_right(self):
        result = tpc.icon("seek-right")
        self.assertEqual(result, tpc.ICONS["seek-right"])

    def test_icon_next(self):
        result = tpc.icon("next")
        self.assertEqual(result, tpc.ICONS["next"])

    def test_icon_skip_start(self):
        result = tpc.icon("skip-start")
        self.assertEqual(result, tpc.ICONS["skip-start"])

    def test_icon_skip_end(self):
        result = tpc.icon("skip-end")
        self.assertEqual(result, tpc.ICONS["skip-end"])

    def test_icon_eject(self):
        result = tpc.icon("eject")
        self.assertEqual(result, tpc.ICONS["eject"])

    def test_icon_vol_muted(self):
        result = tpc.icon("vol-muted")
        self.assertEqual(result, tpc.ICONS["vol-muted"])

    def test_icon_vol_low(self):
        result = tpc.icon("vol-low")
        self.assertEqual(result, tpc.ICONS["vol-low"])

    def test_icon_vol_med(self):
        result = tpc.icon("vol-med")
        self.assertEqual(result, tpc.ICONS["vol-med"])

    def test_icon_vol_high(self):
        result = tpc.icon("vol-high")
        self.assertEqual(result, tpc.ICONS["vol-high"])

    def test_icon_shuffle(self):
        result = tpc.icon("shuffle")
        self.assertEqual(result, tpc.ICONS["shuffle"])

    def test_icon_repeat(self):
        result = tpc.icon("repeat")
        self.assertEqual(result, tpc.ICONS["repeat"])

    def test_icon_repeat_one(self):
        result = tpc.icon("repeat-one")
        self.assertEqual(result, tpc.ICONS["repeat-one"])


def make_metadata(**kwargs):
    """Create a 39-field prefixed metadata string with leading newline."""
    defaults = {
        "volume": "0.0",
        "explicit": "false",
        "loopStatus": "None",
        "loop": "None",
        "shuffle": "false",
    }
    fields = {**defaults, **kwargs}
    return "\n" + "\n".join(
        f"@{i}@{fields.get(f, '')}" for i, f in enumerate(tpc.METADATA_FIELDS)
    )


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
            shuffle="false",
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
            player="mpd", status="Stopped", position="0", length="0", volume="0.0"
        )
        result = tpc.parse_metadata(raw)

        self.assertEqual(result["player"], "mpd")
        self.assertEqual(result["status"], "Stopped")
        self.assertEqual(result["title"], "")
        self.assertEqual(result["artist"], "")
        self.assertEqual(result["album"], "")

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

    def test_metadata_fields_has_40_elements(self):
        """METADATA_FIELDS should have exactly 40 elements."""
        self.assertEqual(len(tpc.METADATA_FIELDS), 40)

    def test_metadata_format_has_prefixes(self):
        """METADATA_FORMAT uses \n@N@ field prefixes for framing."""
        self.assertTrue(tpc.METADATA_FORMAT.startswith("\n"))
        self.assertIn("\n@0@{{playerName}}", tpc.METADATA_FORMAT)
        self.assertIn("\n@1@{{status}}", tpc.METADATA_FORMAT)
        self.assertIn("\n@6@{{xesam:trackNumber}}", tpc.METADATA_FORMAT)
        self.assertIn("\n@7@{{xesam:trackCount}}", tpc.METADATA_FORMAT)
        self.assertIn("\n@39@{{mpris:trackid}}", tpc.METADATA_FORMAT)

    def test_metadata_parse_prefixed_format(self):
        """parse_metadata should handle @N@ prefixed format correctly."""
        raw = make_metadata(player="spotify", status="Playing", title="Test Song")
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["player"], "spotify")
        self.assertEqual(result["status"], "Playing")
        self.assertEqual(result["title"], "Test Song")

    def test_metadata_parse_preserves_newlines_in_fields(self):
        """Fields with embedded newlines are parsed correctly."""
        raw = make_metadata(
            player="spotify", status="Playing", title="Song", artist="Multi\nLine\nArtist"
        )
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["player"], "spotify")
        self.assertEqual(result["artist"], "Multi\nLine\nArtist")

    def test_metadata_parse_invalid_position(self):
        """Invalid position float returns empty dict."""
        raw = make_metadata(position="not_a_number")
        result = tpc.parse_metadata(raw)
        self.assertEqual(result, {})

    def test_metadata_parse_invalid_length(self):
        """Invalid length float returns empty dict."""
        raw = make_metadata(length="also_invalid")
        result = tpc.parse_metadata(raw)
        self.assertEqual(result, {})

    def test_metadata_parse_partial_fields(self):
        """Player sends only non-empty fields - partial parse works."""
        # Player sends only the fields it has; empty fields are omitted
        # Simulate: spotify sends @0@spotify, @1@Playing, @2@Title, @3@Artist
        # (Not all 39 fields)
        raw = "\n@0@spotify\n@1@Playing\n@2@Test Song\n@3@Test Artist"
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["player"], "spotify")
        self.assertEqual(result["status"], "Playing")
        self.assertEqual(result["title"], "Test Song")
        self.assertEqual(result["artist"], "Test Artist")


class TestVolumeIcon(unittest.TestCase):
    """Test _volume_icon() - returns icon name for volume level."""

    def test_volume_icon_muted(self):
        result = tpc._volume_icon(0)
        self.assertEqual(result, "vol-muted")

    def test_volume_icon_low(self):
        result = tpc._volume_icon(32)
        self.assertEqual(result, "vol-low")

    def test_volume_icon_medium(self):
        result = tpc._volume_icon(65)
        self.assertEqual(result, "vol-med")

    def test_volume_icon_high(self):
        result = tpc._volume_icon(100)
        self.assertEqual(result, "vol-high")


class TestLayout(unittest.TestCase):
    """Test layout concerns - positioning and width."""

    def test_row_with_icon_and_text_fits_width(self):
        """Icon + text should fit in row width."""
        icon = tpc.icon("playing")
        text = "Test Song Title"
        result = tpc.row((f"{icon:<4}", 4, "<"), (f"{text:<20}", 20, "^"))
        # Just check it has borders
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))

    def test_row_with_progress_bar_fits_width(self):
        """Progress bar should fit in row width."""
        bar = tpc.progress_bar(30.0, 100.0, 40)
        result = tpc.row((bar, 40, "^"))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))

    def test_row_with_volume_bar_fits_width(self):
        """Volume bar should fit in row width."""
        bar = tpc.volume_bar(50, 40)
        result = tpc.row((bar, 40, "^"))
        self.assertTrue(strip_visible(result).startswith("│ "))
        self.assertTrue(strip_visible(result).endswith(" │"))

    def test_row_all_slots_total_width(self):
        """Row contains icon and title content."""
        icon = tpc.icon("playing")
        result = tpc.row((f"{icon:<4}", 4, "<"), (f"{'Test Title':<10}", 10, "^"))

        self.assertIn("⏵", result)
        self.assertIn("Test Title", result)


class TestRenderUI(unittest.TestCase):
    """Test render_ui() - dynamic row building."""

    def setUp(self):
        # Save original state
        self._orig_players = tpc.s.available_players
        self._orig_state = tpc.s.state
        # Create fresh state
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.player = "spotify"
        tpc.s.state.status = "Playing"
        tpc.s.state.position = 60.0
        tpc.s.state.length = 180.0
        tpc.s.state.volume = 75
        tpc.s.available_players = ["spotify"]

    def tearDown(self):
        tpc.s.state = self._orig_state
        tpc.s.available_players = self._orig_players

    def test_render_ui_all_fields_present(self):
        """All metadata fields present - all info rows rendered."""
        tpc.s.state.title = "Test Song"
        tpc.s.state.artist = "Test Artist"
        tpc.s.state.album = "Test Album"
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
        tpc.s.state.title = "Test Song"
        tpc.s.state.artist = "Test Artist"
        tpc.s.state.album = ""
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
        tpc.s.state.title = ""
        tpc.s.state.artist = "Test Artist"
        tpc.s.state.album = "Test Album"
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
        tpc.s.state.title = "Test Song"
        tpc.s.state.artist = ""
        tpc.s.state.album = "Test Album"
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
        tpc.s.state.title = "Test Song"
        tpc.s.state.artist = "Test Artist"
        tpc.s.state.album = ""
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
        tpc.s.state.title = "Test Song"
        tpc.s.state.artist = "Test Artist"
        tpc.s.state.album = "Test Album"
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
        tpc.s.state.title = ""
        tpc.s.state.artist = ""
        tpc.s.state.album = ""
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
        old_bg = os.environ.pop("TPCTL_BG", None)
        try:
            spec = importlib.util.spec_from_file_location(
                "tpc2", "../tmux-player-ctl.py"
            )
            tpc2 = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(tpc2)
            # Should be just \033[0m
            self.assertEqual(tpc2.Theme.RESET, "\033[0m")
        finally:
            if old_bg:
                os.environ["TPCTL_BG"] = old_bg

    def test_reset_with_bg(self):
        """With BG set, RESET includes background color."""
        import importlib
        import importlib.util
        import os

        os.environ["TPCTL_BG"] = "30;30;50"
        try:
            spec = importlib.util.spec_from_file_location(
                "tpc3", "../tmux-player-ctl.py"
            )
            tpc3 = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(tpc3)
            # Should be \033[0m followed by background
            self.assertEqual(tpc3.Theme.RESET, "\033[0m\033[48;2;30;30;50m")
        finally:
            del os.environ["TPCTL_BG"]


class TestTrackRow(unittest.TestCase):
    """Test track_row() - track name with optional track number display."""

    def setUp(self):
        # Save original state
        self._orig_players = tpc.s.available_players
        self._orig_state = tpc.s.state
        self._orig_ui_width = tpc.Config.UI_WIDTH
        # Create fresh state
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.player = "spotify"
        tpc.s.state.status = "Playing"
        tpc.s.state.position = 60.0
        tpc.s.state.length = 180.0
        tpc.s.state.volume = 75
        tpc.s.available_players = ["spotify"]

    def tearDown(self):
        tpc.s.state = self._orig_state
        tpc.s.available_players = self._orig_players
        tpc.Config.UI_WIDTH = self._orig_ui_width

    def test_calc_track_num_width_single_digit(self):
        """_calc_track_num_width should return correct width for single digit."""
        result = tpc._calc_track_num_width(5)
        self.assertEqual(result, 5)  # "5 / 5" = 5 chars

    def test_calc_track_num_width_double_digit(self):
        """_calc_track_num_width should return correct width for double digits."""
        result = tpc._calc_track_num_width(12)
        self.assertEqual(result, 7)  # "12 / 12" = 7 chars

    def test_calc_track_num_width_large_count(self):
        """_calc_track_num_width should handle large track counts (1000+)."""
        result = tpc._calc_track_num_width(1000)
        self.assertEqual(result, 11)  # "1000 / 1000" = 11 chars

    def test_calc_track_num_width_zero(self):
        """_calc_track_num_width should return 0 for zero."""
        result = tpc._calc_track_num_width(0)
        self.assertEqual(result, 0)

    def test_track_row_has_label(self):
        """Track row should always have the 'Track:' label."""
        tpc.s.state.title = "Test Song"
        tpc.s.state.trackNumber = ""
        result = tpc.track_row()
        self.assertIn("Track:", result)

    def test_track_row_has_title(self):
        """Track row should display the track title."""
        tpc.s.state.title = "My Awesome Song"
        tpc.s.state.trackNumber = ""
        result = tpc.track_row()
        self.assertIn("My Awesome Song", result)

    def test_track_row_shows_track_number_when_present(self):
        """Track row should display track number when available."""
        tpc.s.state.title = "Test Song"
        tpc.s.state.trackNumber = "5"
        tpc.s.state.trackCount = 12
        result = tpc.track_row()
        # Should show track number in "X / Y" format
        self.assertIn("5", result)
        # Should show total tracks if available
        self.assertIn("12", result)

    def test_track_row_hides_track_number_when_absent(self):
        """Track row should not show track number when not available."""
        tpc.s.state.title = "Test Song"
        tpc.s.state.trackNumber = ""
        tpc.s.state.trackCount = 0
        result = tpc.track_row()
        # Should still have the title
        self.assertIn("Test Song", result)
        # Should NOT have " / " pattern (which indicates track count display)
        # The track number area should be empty or just spaces
        visible = strip_visible(result)
        # The " / " separator should not appear when track number is absent
        self.assertNotIn(" / ", visible)

    def test_track_row_hides_track_number_when_count_missing(self):
        """Track row should NOT show track number when trackCount is unavailable."""
        tpc.s.state.title = "Test Song"
        tpc.s.state.trackNumber = "3"
        tpc.s.state.trackCount = 0
        result = tpc.track_row()
        visible = strip_visible(result)
        # Should NOT show the track number (no / pattern)
        self.assertNotIn(" / ", visible)
        # Title should still be shown
        self.assertIn("Test Song", visible)

    def test_track_row_truncates_long_title_with_track_number(self):
        """Long track titles should be truncated when track number is shown."""
        tpc.s.state.title = "This Is A Very Long Song Title That Should Be Truncated"
        tpc.s.state.trackNumber = "7"
        tpc.s.state.trackCount = 10
        result = tpc.track_row()
        # Title should be truncated (ends with ellipsis)
        visible = strip_visible(result)
        # The full long title should NOT be in the output
        self.assertNotIn("This Is A Very Long Song Title That Should Be Truncated", visible)

    def test_track_row_handles_numeric_track_number(self):
        """Track row should handle numeric track numbers correctly."""
        tpc.s.state.title = "Track 1"
        tpc.s.state.trackNumber = 1
        tpc.s.state.trackCount = 10
        result = tpc.track_row()
        self.assertIn("1", result)
        self.assertIn("10", result)

    def test_track_row_handles_string_track_number(self):
        """Track row should handle string track numbers correctly."""
        tpc.s.state.title = "Track 2"
        tpc.s.state.trackNumber = "2"
        tpc.s.state.trackCount = "15"
        result = tpc.track_row()
        self.assertIn("2", result)
        self.assertIn("15", result)

    def test_track_row_empty_title_with_track_number(self):
        """Track row should show track number even when title is empty."""
        tpc.s.state.title = ""
        tpc.s.state.trackNumber = "9"
        tpc.s.state.trackCount = 12
        result = tpc.track_row()
        # Should still have label and track number
        self.assertIn("Track:", result)
        self.assertIn("9", result)

    def test_track_row_preserves_borders(self):
        """Track row should maintain proper border formatting."""
        tpc.s.state.title = "Test Song"
        tpc.s.state.trackNumber = "1"
        tpc.s.state.trackCount = 10
        result = tpc.track_row()
        visible = strip_visible(result)
        self.assertTrue(visible.startswith("│ "))
        self.assertTrue(visible.endswith(" │"))

    def test_track_row_track_count_format(self):
        """Track row should display in 'X / Y' format when both values present."""
        tpc.s.state.title = "Song"
        tpc.s.state.trackNumber = "4"
        tpc.s.state.trackCount = 8
        result = tpc.track_row()
        visible = strip_visible(result)
        # Should have "4 / 8" or similar format
        self.assertIn(" / ", visible)
        self.assertIn("4", visible)
        self.assertIn("8", visible)

    def test_track_row_handles_large_track_count(self):
        """Track row should handle albums with 100+ tracks."""
        tpc.s.state.title = "Epic Song"
        tpc.s.state.trackNumber = "99"
        tpc.s.state.trackCount = 150
        result = tpc.track_row()
        visible = strip_visible(result)
        # Should show "99 / 150"
        self.assertIn("99", visible)
        self.assertIn("150", visible)
        self.assertIn(" / ", visible)

    def test_track_row_handles_string_track_count(self):
        """Track row should handle string track counts (e.g., from metadata)."""
        tpc.s.state.title = "Song"
        tpc.s.state.trackNumber = "7"
        tpc.s.state.trackCount = "12"  # String instead of int
        result = tpc.track_row()
        visible = strip_visible(result)
        # Should show "7 / 12"
        self.assertIn("7", visible)
        self.assertIn("12", visible)
        self.assertIn(" / ", visible)

    def test_track_row_hides_track_number_when_count_invalid(self):
        """Track row should NOT show track number when trackCount is invalid."""
        tpc.s.state.title = "Song"
        tpc.s.state.trackNumber = "3"
        tpc.s.state.trackCount = "invalid"  # Invalid string
        # Should not raise exception, just show title without track number
        result = tpc.track_row()
        visible = strip_visible(result)
        # Should NOT show the track number (no / pattern)
        self.assertNotIn(" / ", visible)
        # Title should still be shown
        self.assertIn("Song", visible)


class TestTrackRowRenderUI(unittest.TestCase):
    """Test track row rendering within full UI output."""

    def setUp(self):
        self._orig_players = tpc.s.available_players
        self._orig_state = tpc.s.state
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.player = "spotify"
        tpc.s.state.status = "Playing"
        tpc.s.state.position = 60.0
        tpc.s.state.length = 180.0
        tpc.s.state.volume = 75
        tpc.s.available_players = ["spotify"]

    def tearDown(self):
        tpc.s.state = self._orig_state
        tpc.s.available_players = self._orig_players

    def test_render_ui_with_track_number(self):
        """UI should show track number when trackNumber is set."""
        tpc.s.state.title = "Famous Song"
        tpc.s.state.artist = "Great Artist"
        tpc.s.state.album = "Best Album"
        tpc.s.state.trackNumber = "3"
        tpc.s.state.trackCount = 12
        import io
        import sys

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            tpc.render_ui()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        # Should show the track number
        self.assertIn("3", output)
        self.assertIn("12", output)

    def test_render_ui_without_track_number(self):
        """UI should not show track number when trackNumber is not set."""
        tpc.s.state.title = "Famous Song"
        tpc.s.state.artist = "Great Artist"
        tpc.s.state.album = "Best Album"
        tpc.s.state.trackNumber = ""
        tpc.s.state.trackCount = 0
        import io
        import sys

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            tpc.render_ui()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        # Should still show track title
        self.assertIn("Famous Song", output)
        # The " / " pattern for track count should not be present
        visible = strip_visible(output)
        self.assertNotIn(" / ", visible)


class TestWideCharacters(unittest.TestCase):
    """Test CJK and wide character handling in truncate() and row()."""

    def test_truncate_cjk_respects_visible_width(self):
        """CJK characters should count as 2 visible columns, not 1."""
        # 8 CJK chars = 16 visible columns
        text = "日本語テスト"  # 6 CJK chars = 12 visible columns
        result = tpc.truncate(text, 10)
        # Should truncate because 12 visible > 10 visible
        self.assertTrue(result.endswith("…"), f"Expected truncation, got: {repr(result)}")

    def test_truncate_cjk_exact_width(self):
        """CJK text exactly fitting visible width should not truncate."""
        text = "日本語"  # 3 CJK chars = 6 visible columns
        result = tpc.truncate(text, 6)
        self.assertEqual(result, text)

    def test_truncate_mixed_ascii_cjk(self):
        """Mix of ASCII (1 col) and CJK (2 col) characters."""
        text = "Hello日本"  # 5 + 2 = 7 visible columns
        result = tpc.truncate(text, 5)
        # Should truncate because 7 visible > 5 visible
        self.assertTrue(result.endswith("…"), f"Expected truncation, got: {repr(result)}")

    def test_row_with_wide_characters_keeps_border(self):
        """Row with CJK content should keep borders at correct position."""
        text = "日本語曲名"  # 6 visible columns (3 CJK chars)
        result = tpc.row((tpc.truncate(text, 10), 10, "^"))
        visible = strip_visible(result)
        # Row should start with border
        self.assertTrue(visible.startswith("│ "), f"Row should start with │: {repr(visible)}")
        # Row should end with border
        self.assertTrue(visible.rstrip().endswith(" │"), f"Row should end with │: {repr(visible)}")
        # Content should be inside borders
        self.assertEqual(visible.count("│"), 2, f"Expected 2 borders, got: {repr(visible)}")

    def test_row_with_long_cjk_title_fits_in_slot(self):
        """Long CJK title truncated should fit in its slot without pushing borders."""
        # Very long CJK text (30+ columns visible)
        text = "永久に回り続ける螺旋階段を登り続ける物語"  # ~20+ visible columns
        truncated = tpc.truncate(text, 20)
        result = tpc.row((truncated, 20, "^"), None, ("Artist", 10, "<"))
        visible = strip_visible(result)
        # Verify borders are at correct positions
        self.assertTrue(visible.startswith("│ "), f"Should start with │: {repr(visible)}")
        self.assertTrue(visible.rstrip().endswith(" │"), f"Should end with │: {repr(visible)}")
        # Content should be present and truncated
        self.assertIn("永久", visible)
        self.assertIn("Artist", visible)

    def test_row_cjk_with_color_preserves_borders(self):
        """CJK text with ANSI colors should not break row formatting."""
        text = "日本語タイトル"  # ~8 visible columns
        colored = f"\x1b[92m{text}\x1b[0m"  # Green CJK text
        truncated = tpc.truncate(colored, 20)
        result = tpc.row((truncated, 20, "^"))
        visible = strip_visible(result)
        # Should have exactly 2 borders
        self.assertEqual(visible.count("│"), 2, f"Expected 2 borders: {repr(visible)}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
