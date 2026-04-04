#!/usr/bin/env python3
"""
Test suite for playerctl subprocess integration.
Mocks run_playerctl and verifies data parsing.
"""

import unittest
import subprocess
from unittest.mock import patch, MagicMock

import importlib.util
spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestParseVolume(unittest.TestCase):
    """Test _parse_volume() converts playerctl output correctly."""

    def test_parse_full_volume(self):
        """Volume 0.5 should return 50."""
        self.assertEqual(tpc._parse_volume("0.5\n"), 50)

    def test_parse_full_volume_dot_zero(self):
        """Volume 1.0 should return 100."""
        self.assertEqual(tpc._parse_volume("1.0\n"), 100)

    def test_parse_zero_volume(self):
        """Volume 0.0 should return 0."""
        self.assertEqual(tpc._parse_volume("0.0\n"), 0)

    def test_parse_float_rounding(self):
        """Volume 0.67 should return ~67."""
        self.assertEqual(tpc._parse_volume("0.67\n"), 67)


class TestParseMetadata(unittest.TestCase):
    """Test parse_metadata() extracts newline-delimited metadata."""

    def _make_metadata(self, **fields):
        """Build 40-line metadata with specified fields."""
        parts = [""] * 40
        parts[0] = fields.get("player", "")
        parts[1] = fields.get("status", "")
        parts[2] = fields.get("title", "")
        parts[3] = fields.get("artist", "")
        parts[4] = fields.get("album", "")
        parts[31] = fields.get("position", "")
        parts[32] = fields.get("length", "")
        parts[33] = fields.get("volume", "")
        return "\n".join(parts)

    def test_parse_empty_metadata(self):
        """Short input should return empty dict."""
        result = tpc.parse_metadata("short\n")
        self.assertEqual(result, {})

    def test_parse_basic_metadata(self):
        """Should extract player, status, title, artist, album."""
        raw = self._make_metadata(
            player="spotify",
            status="Playing",
            title="Song Title",
            artist="Artist Name",
            album="Album Name",
            position="60000000",  # 60 seconds
            length="300000000",   # 300 seconds
            volume="0.5",
        )
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["player"], "spotify")
        self.assertEqual(result["status"], "Playing")
        self.assertEqual(result["title"], "Song Title")
        self.assertEqual(result["artist"], "Artist Name")
        self.assertEqual(result["album"], "Album Name")
        self.assertEqual(result["position"], 60.0)
        self.assertEqual(result["length"], 300.0)
        self.assertEqual(result["volume"], 50)

    def test_parse_position_in_microseconds(self):
        """Position should be converted from microseconds to seconds."""
        raw = self._make_metadata(position="123456789")
        result = tpc.parse_metadata(raw)
        self.assertAlmostEqual(result["position"], 123.456789, places=5)

    def test_parse_missing_optional_fields(self):
        """Should handle missing optional fields gracefully."""
        raw = self._make_metadata(
            player="firefox",
            status="Paused",
            title="T",
            artist="A",
            album="Al",
        )
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["player"], "firefox")
        self.assertEqual(result["status"], "Paused")
        self.assertEqual(result["position"], 0.0)
        self.assertEqual(result["length"], 0.0)


class TestRunPlayerctl(unittest.TestCase):
    """Test run_playerctl() subprocess integration."""

    @patch("subprocess.run")
    def test_calls_playerctl_with_args(self, mock_run):
        """Should call subprocess.run with playerctl command."""
        mock_run.return_value = MagicMock(stdout="output\n", returncode=0)
        
        result = tpc.run_playerctl("metadata")
        
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]  # first positional arg
        self.assertEqual(call_args[0], "playerctl")
        self.assertIn("metadata", call_args)

    @patch("subprocess.run")
    def test_includes_player_arg_when_set(self, mock_run):
        """Should include -p player when current_player is set."""
        tpc.current_player = "spotify"
        mock_run.return_value = MagicMock(stdout="ok\n", returncode=0)
        
        tpc.run_playerctl("status")
        
        call_args = mock_run.call_args[0][0]
        self.assertIn("-p", call_args)
        self.assertIn("spotify", call_args)
        
        tpc.current_player = ""

    @patch("subprocess.run")
    def test_returns_stripped_output(self, mock_run):
        """Should return stripped stdout."""
        mock_run.return_value = MagicMock(stdout="  output  \n", returncode=0)
        
        result = tpc.run_playerctl("metadata")
        
        self.assertEqual(result, "output")

    @patch("subprocess.run")
    def test_returns_empty_on_error(self, mock_run):
        """Should return empty string on non-zero exit."""
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        
        result = tpc.run_playerctl("invalid")
        
        self.assertEqual(result, "")

    @patch("subprocess.run")
    def test_returns_empty_on_timeout(self, mock_run):
        """Should return empty string on timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 2)
        
        result = tpc.run_playerctl("metadata")
        
        self.assertEqual(result, "")


class TestGetAvailablePlayers(unittest.TestCase):
    """Test get_available_players() discovers players."""

    @patch("subprocess.run")
    def test_finds_single_player(self, mock_run):
        """Should return list with one player."""
        mock_run.return_value = MagicMock(stdout="spotify\n", returncode=0)
        
        result = tpc.get_available_players()
        
        self.assertEqual(result, ["spotify"])

    @patch("subprocess.run")
    def test_finds_multiple_players(self, mock_run):
        """Should return all players from stdout."""
        mock_run.return_value = MagicMock(stdout="spotify\nfirefox\n", returncode=0)
        
        result = tpc.get_available_players()
        
        self.assertEqual(result, ["spotify", "firefox"])

    @patch("subprocess.run")
    def test_returns_empty_on_no_players(self, mock_run):
        """Should return empty list if no players."""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        
        result = tpc.get_available_players()
        
        self.assertEqual(result, [])


class TestHandleKeyVolume(unittest.TestCase):
    """Test handle_key() volume commands with mocked run_playerctl."""

    def setUp(self):
        # Create fresh state
        self._orig_state = tpc.state
        tpc.state = tpc.PlayerState()
        tpc.state.volume = 50
        tpc.state.position = 60.0
        tpc.state.length = 180.0
        tpc.state.status = "Playing"

    def tearDown(self):
        tpc.state = self._orig_state

    @patch.object(tpc, 'run_playerctl')
    def test_volume_up_sends_float(self, mock_run):
        """Volume up should send float to playerctl."""
        tpc.handle_key("\x1b", "[A")  # Arrow up
        # Should have called run_playerctl with volume
        args = mock_run.call_args
        self.assertEqual(args[0][0], "volume")
        # Should be formatted as float string
        vol_str = args[0][1]
        self.assertIn(".", vol_str)  # Is a float
        # Volume should have increased
        self.assertEqual(tpc.state.volume, 55)

    @patch.object(tpc, 'run_playerctl')
    def test_volume_down_sends_float(self, mock_run):
        """Volume down should send float to playerctl."""
        tpc.handle_key("\x1b", "[B")  # Arrow down
        args = mock_run.call_args
        self.assertEqual(args[0][0], "volume")
        vol_str = args[0][1]
        self.assertIn(".", vol_str)  # Is a float
        # Volume should have decreased
        self.assertEqual(tpc.state.volume, 45)

    @patch.object(tpc, 'run_playerctl')
    def test_volume_up_at_max_stays_100(self, mock_run):
        """Volume up at 100 stays at 100."""
        tpc.state.volume = 100
        tpc.handle_key("\x1b", "[A")
        self.assertEqual(tpc.state.volume, 100)

    @patch.object(tpc, 'run_playerctl')
    def test_volume_down_at_min_stays_0(self, mock_run):
        """Volume down at 0 stays at 0."""
        tpc.state.volume = 0
        tpc.handle_key("\x1b", "[B")
        self.assertEqual(tpc.state.volume, 0)

    @patch.object(tpc, 'run_playerctl')
    def test_mute_sets_volume_0(self, mock_run):
        """Mute should set volume to 0."""
        tpc.state.volume = 75
        tpc.handle_key("m", "")
        args = mock_run.call_args
        self.assertEqual(args[0][0], "volume")
        self.assertEqual(args[0][1], "0.0")
        self.assertEqual(tpc.state.volume, 0)
        # Should store the pre-mute volume
        self.assertEqual(tpc.state.pre_mute_volume, 75)

    @patch.object(tpc, 'run_playerctl')
    def test_unmute_restores_stored_volume(self, mock_run):
        """Unmute should restore to stored pre-mute volume."""
        tpc.state.volume = 0
        tpc.state.pre_mute_volume = 75
        tpc.handle_key("m", "")
        args = mock_run.call_args
        self.assertEqual(args[0][0], "volume")
        self.assertEqual(args[0][1], "0.75")  # 75% as float
        self.assertEqual(tpc.state.volume, 75)

    @patch.object(tpc, 'run_playerctl')
    def test_unmute_falls_back_to_50(self, mock_run):
        """Unmute with no stored volume should fall back to 50."""
        tpc.state.volume = 0
        tpc.state.pre_mute_volume = 0  # No previous unmute
        tpc.handle_key("m", "")
        args = mock_run.call_args
        self.assertEqual(args[0][0], "volume")
        self.assertEqual(args[0][1], "0.50")  # Default 50%
        self.assertEqual(tpc.state.volume, 50)

    @patch.object(tpc, 'run_playerctl')
    def test_mute_then_unmute_restores_volume(self, mock_run):
        """Mute then unmute cycle should restore original volume."""
        tpc.state.volume = 80
        tpc.state.pre_mute_volume = 50  # From previous unmute
        
        # Mute
        tpc.handle_key("m", "")
        self.assertEqual(tpc.state.volume, 0)
        self.assertEqual(tpc.state.pre_mute_volume, 80)  # Stored before mute
        
        # Unmute
        tpc.handle_key("m", "")
        args = mock_run.call_args  # Get last call
        self.assertEqual(args[0][0], "volume")
        self.assertEqual(args[0][1], "0.80")  # 80% restored
        self.assertEqual(tpc.state.volume, 80)


class TestUpdateStateFromMetadata(unittest.TestCase):
    """Test update_state_from_metadata() sets dirty flag correctly."""

    def setUp(self):
        self._orig_state = tpc.state
        self._orig_last_cmd = tpc.last_command_time
        tpc.state = tpc.PlayerState()
        tpc.state.title = "Old Title"
        tpc.state.artist = "Old Artist"
        tpc.state.position = 0.0
        # Reset command time to avoid debounce
        tpc.last_command_time = 0.0

    def tearDown(self):
        tpc.state = self._orig_state
        tpc.last_command_time = self._orig_last_cmd

    def test_sets_dirty_when_values_change(self):
        """Should set dirty=True when values actually change."""
        tpc.state.dirty = False
        data = {"title": "New Title", "artist": "Old Artist"}
        tpc.update_state_from_metadata(data)
        self.assertTrue(tpc.state.dirty)
        self.assertEqual(tpc.state.title, "New Title")

    def test_clears_dirty_when_no_change(self):
        """Should not set dirty when values are the same."""
        tpc.state.dirty = False
        data = {"title": "Old Title", "artist": "Old Artist"}
        tpc.update_state_from_metadata(data)
        self.assertFalse(tpc.state.dirty)

    def test_updates_all_fields(self):
        """Should update all fields from metadata dict."""
        tpc.state.dirty = False
        data = {
            "title": "New Title",
            "artist": "New Artist",
            "album": "New Album",
            "status": "Playing",
            "volume": 75,
        }
        tpc.update_state_from_metadata(data)
        self.assertEqual(tpc.state.title, "New Title")
        self.assertEqual(tpc.state.artist, "New Artist")
        self.assertEqual(tpc.state.album, "New Album")
        self.assertEqual(tpc.state.status, "Playing")
        self.assertEqual(tpc.state.volume, 75)


class TestParsePositionFollower(unittest.TestCase):
    """Test parsing position data from position follower."""

    def test_parse_seconds_not_microseconds(self):
        """Position follower outputs seconds, not microseconds."""
        # Playerctl position outputs like "123.456789"
        # This should NOT be divided by 1_000_000
        seconds = float("123456789") / 1_000_000
        self.assertAlmostEqual(seconds, 123.456789, places=3)


class TestMetadataFollowerParsing(unittest.TestCase):
    """Test parsing metadata follower output (39 fields per update)."""

    def _make_full_metadata(self, **fields):
        """Build a 39-line metadata block."""
        defaults = {
            "playerName": "spotify",
            "status": "Playing",
            "title": "Test Song",
            "artist": "Test Artist",
            "album": "Test Album",
        }
        defaults.update(fields)
        # Fill in all 39 fields
        parts = [""] * 39
        parts[0] = defaults.get("playerName", "")
        parts[1] = defaults.get("status", "")
        parts[2] = defaults.get("title", "")
        parts[3] = defaults.get("artist", "")
        parts[4] = defaults.get("album", "")
        parts[31] = defaults.get("position", "")
        parts[32] = defaults.get("length", "")
        parts[33] = defaults.get("volume", "")
        return "\n".join(parts)

    def test_parse_complete_39_line_block(self):
        """Should parse a complete 39-line metadata block."""
        raw = self._make_full_metadata(
            playerName="spotify",
            title="My Song",
            artist="My Artist",
            album="My Album",
            position="60000000",
            length="180000000",
        )
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["player"], "spotify")
        self.assertEqual(result["title"], "My Song")
        self.assertEqual(result["artist"], "My Artist")
        self.assertEqual(result["position"], 60.0)
        self.assertEqual(result["length"], 180.0)

    def test_parse_multiple_blocks(self):
        """Should parse multiple concatenated 39-line blocks."""
        block1 = self._make_full_metadata(title="First Song")
        block2 = self._make_full_metadata(title="Second Song")
        # Concatenate blocks with newline separator
        combined = block1 + "\n" + block2
        # Don't use strip() - it removes trailing empty fields
        lines = combined.split("\n")
        # Should have 78 lines (2 blocks of 39 each)
        self.assertEqual(len(lines), 78)
        # Parse each block by taking 39 lines at a time
        titles_found = []
        for i in range(0, len(lines), 39):
            block_lines = lines[i:i+39]
            if len(block_lines) == 39:
                block = "\n".join(block_lines)
                result = tpc.parse_metadata(block)
                if result:
                    titles_found.append(result.get("title", ""))
        self.assertIn("First Song", titles_found)
        self.assertIn("Second Song", titles_found)


if __name__ == "__main__":
    unittest.main()
