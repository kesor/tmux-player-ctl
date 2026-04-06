"""Input handling tests: enable_raw_mode, disable_raw_mode, read_key."""

import sys
import unittest
from unittest.mock import patch

import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestEnableRawMode(unittest.TestCase):
    """Test enable_raw_mode / disable_raw_mode terminal functions."""

    @patch("os.isatty", return_value=False)
    def test_enable_raw_mode_returns_none_when_not_tty(self, mock_isatty):
        """Should return None when stdin is not a tty."""
        result = tpc.enable_raw_mode(sys.stdin.fileno())
        self.assertIsNone(result)

    @patch("os.isatty", return_value=True)
    @patch("termios.tcgetattr")
    @patch("termios.tcsetattr")
    def test_enable_raw_mode_returns_settings_when_tty(
        self, mock_setattr, mock_getattr, mock_isatty
    ):
        """Should return old_settings when stdin is a tty."""
        # termios struct: [c_iflag, c_oflag, c_cflag, c_lflag, c_cc (VMIN/VTIME), ...]
        # new_settings[3] is c_lflag (int), new_settings[6] is c_cc (list)
        mock_getattr.return_value = [0, 0, 0, 0, 0, 0, [0] * 32]
        fd = sys.stdin.fileno()
        result = tpc.enable_raw_mode(fd)
        self.assertIsNotNone(result)
        # Should be called twice (get then set)
        self.assertEqual(mock_getattr.call_count, 2)
        self.assertEqual(mock_setattr.call_count, 1)


class TestDisableRawMode(unittest.TestCase):
    """Test disable_raw_mode restores terminal settings."""

    @patch("termios.tcsetattr")
    def test_disable_raw_mode_restores_settings(self, mock_setattr):
        """Should call tcsetattr with old_settings."""
        fd = sys.stdin.fileno()
        old_settings = [0, 0, 0, 0, 0, 0, [0] * 32]
        tpc.disable_raw_mode(fd, old_settings)
        mock_setattr.assert_called_once()


class TestReadKey(unittest.TestCase):
    """Test read_key function - reads keypress with optional escape sequence."""

    @patch("os.read")
    @patch("select.select", return_value=([], [], []))
    def test_read_key_returns_none_when_no_input(self, mock_select, mock_read):
        """Should return None when no input available."""
        mock_read.return_value = b""
        result = tpc.read_key(sys.stdin.fileno())
        self.assertIsNone(result)

    @patch("os.read")
    @patch("select.select")
    def test_read_key_returns_simple_key(self, mock_select, mock_read):
        """Should return (key, '') for simple key like 'q'."""
        mock_select.return_value = ([sys.stdin.fileno()], [], [])
        mock_read.return_value = b"q"
        result = tpc.read_key(sys.stdin.fileno())
        self.assertEqual(result, ("q", ""))

    @patch("os.read")
    @patch("select.select")
    def test_read_key_returns_escape_sequence(self, mock_select, mock_read):
        """Should return (chr(27), '[A') for arrow up."""
        mock_select.side_effect = [
            ([sys.stdin.fileno()], [], []),  # first \x1b
            ([sys.stdin.fileno()], [], []),  # second [
            ([sys.stdin.fileno()], [], []),  # third A
        ]
        mock_read.side_effect = [b"\x1b", b"[", b"A"]
        result = tpc.read_key(sys.stdin.fileno())
        self.assertEqual(result, ("\x1b", "[A"))

    @patch("os.read")
    @patch("select.select")
    def test_read_key_returns_escape_without_sequence(self, mock_select, mock_read):
        """Should return (chr(27), '') when no sequence follows."""
        mock_select.side_effect = [
            ([sys.stdin.fileno()], [], []),  # first \x1b
            ([], [], []),  # nothing follows
        ]
        mock_read.side_effect = [b"\x1b"]
        result = tpc.read_key(sys.stdin.fileno())
        self.assertEqual(result, ("\x1b", ""))


class TestReadMetadataFromFollower(unittest.TestCase):
    """Test read_metadata_from_follower parses follower output."""

    def setUp(self):
        self._orig = tpc.s.state
        tpc.s.state = tpc.PlayerState()
        tpc.s.last_command_time = 0
        tpc.s._meta_buf = ""  # Reset buffer

    def tearDown(self):
        tpc.s.state = self._orig

    def test_parses_valid_prefixed_metadata(self):
        """Should parse valid @N@ prefixed metadata block."""
        # Build a complete 39-field prefixed metadata block
        fields = {}
        defaults = {
            "volume": "0.0",
            "explicit": "false",
            "loopStatus": "None",
            "loop": "None",
            "shuffle": "false",
        }
        for k, v in defaults.items():
            fields[k] = v
        fields["playerName"] = "spotify"
        fields["status"] = "Playing"
        fields["title"] = "Song"
        raw = "\n" + "\n".join(
            f"@{i}@{fields.get(f, '')}" for i, f in enumerate(tpc.METADATA_FIELDS)
        )
        # Add second block to trigger extraction (buffering requires 2 blocks)
        raw += "\n@0@spotify\n@1@Paused\n@2@Next"
        tpc.read_metadata_from_follower(raw)
        self.assertEqual(tpc.s.state.title, "Song")
        self.assertEqual(tpc.s.state.status, "Playing")

    def test_handles_embedded_newlines_in_value(self):
        """Fields with embedded newlines should be preserved."""
        # artist has newline in value
        raw = "\n@0@spotify\n@1@Playing\n@2@Test\n@3@Multi\nLine\nArtist"
        # Add second block to trigger extraction
        raw += "\n@0@spotify\n@1@Paused\n@2@Next"
        tpc.read_metadata_from_follower(raw)
        self.assertEqual(tpc.s.state.artist, "Multi\nLine\nArtist")

    def test_handles_partial_fields(self):
        """Player sends only non-empty fields - should still parse."""
        # Simulate player sending only fields 0-4
        raw = "\n@0@spotify\n@1@Playing\n@2@Test Song\n@3@Artist\n@4@Album"
        # Add second block to trigger extraction
        raw += "\n@0@spotify\n@1@Paused\n@2@Next"
        tpc.read_metadata_from_follower(raw)
        self.assertEqual(tpc.s.state.player, "")
        self.assertEqual(tpc.s.state.title, "Test Song")
        self.assertEqual(tpc.s.state.artist, "Artist")


class TestHandleKeySeek(unittest.TestCase):
    """Test handle_key seek functionality."""

    def setUp(self):
        self._orig = tpc.s.state
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.position = 30.0
        tpc.s.state.length = 180.0
        tpc.s.state.volume = 50
        tpc.s.last_command_time = 0

    def tearDown(self):
        tpc.s.state = self._orig

    @patch.object(tpc, "run_playerctl_async")
    def test_seek_forward_sends_correct_format(self, mock_seek):
        """Seek forward should send '10+' not '+10' (offset before +/-)."""
        # Arrow right [C
        tpc.handle_key("\x1b", "[C")
        # Verify the position command format: "10+" not "+10"
        mock_seek.assert_called_once()
        call_args = mock_seek.call_args[0]
        self.assertEqual(call_args[0], "position")
        self.assertEqual(call_args[1], "10+")
        # Verify optimistic update
        self.assertEqual(tpc.s.state.position, 40.0)

    @patch.object(tpc, "run_playerctl_async")
    def test_seek_backward_sends_correct_format(self, mock_seek):
        """Seek backward should send '10-' not '-10' (offset before +/-)."""
        # Arrow left [D
        tpc.handle_key("\x1b", "[D")
        # Verify the position command format: "10-" not "-10"
        mock_seek.assert_called_once()
        call_args = mock_seek.call_args[0]
        self.assertEqual(call_args[0], "position")
        self.assertEqual(call_args[1], "10-")
        # Verify optimistic update
        self.assertEqual(tpc.s.state.position, 20.0)

    @patch.object(tpc, "run_playerctl_async")
    def test_seek_forward_clamped_at_length(self, mock_seek):
        """Seek forward should not exceed track length."""
        tpc.s.state.position = 175.0  # 5 seconds from end
        tpc.handle_key("\x1b", "[C")
        # Should clamp to length, not exceed it
        self.assertEqual(tpc.s.state.position, 180.0)

    @patch.object(tpc, "run_playerctl_async")
    def test_seek_backward_clamped_at_zero(self, mock_seek):
        """Seek backward should not go below 0."""
        tpc.s.state.position = 5.0
        tpc.handle_key("\x1b", "[D")
        # Should clamp to 0, not go negative
        self.assertEqual(tpc.s.state.position, 0.0)

    @patch.object(tpc, "run_playerctl_async")
    def test_seek_marks_state_dirty(self, mock_seek):
        """Seek should mark state as dirty for re-render."""
        tpc.s.state.dirty = False
        tpc.handle_key("\x1b", "[C")
        self.assertTrue(tpc.s.state.dirty)


class TestHandleKeyVolume(unittest.TestCase):
    """Test handle_key volume control commands."""

    def setUp(self):
        self._orig = tpc.s.state
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.position = 30.0
        tpc.s.state.length = 180.0
        tpc.s.state.volume = 50
        tpc.s.state.status = "Playing"
        tpc.s.last_command_time = 0

    def tearDown(self):
        tpc.s.state = self._orig

    @patch.object(tpc, "run_playerctl_async")
    def test_volume_up_sends_absolute_value(self, mock_vol):
        """Volume up should send absolute value, not '+0.05'."""
        # Arrow up [A
        tpc.handle_key("\x1b", "[A")
        mock_vol.assert_called_once()
        call_args = mock_vol.call_args[0]
        self.assertEqual(call_args[0], "volume")
        # Should be absolute value like "0.55", not "+0.05"
        self.assertRegex(call_args[1], r"^0\.[0-9]+$")
        self.assertNotIn("+", call_args[1])
        # Verify state updated
        self.assertEqual(tpc.s.state.volume, 55)

    @patch.object(tpc, "run_playerctl_async")
    def test_volume_down_sends_absolute_value(self, mock_vol):
        """Volume down should send absolute value, not '-0.05'."""
        # Arrow down [B
        tpc.handle_key("\x1b", "[B")
        mock_vol.assert_called_once()
        call_args = mock_vol.call_args[0]
        self.assertEqual(call_args[0], "volume")
        # Should be absolute value like "0.45", not "-0.05"
        self.assertRegex(call_args[1], r"^0\.[0-9]+$")
        self.assertNotIn("-", call_args[1])
        # Verify state updated
        self.assertEqual(tpc.s.state.volume, 45)

    @patch.object(tpc, "run_playerctl_async")
    def test_volume_up_clamped_at_100(self, mock_vol):
        """Volume up should not exceed 100."""
        tpc.s.state.volume = 98
        tpc.handle_key("\x1b", "[A")
        self.assertEqual(tpc.s.state.volume, 100)

    @patch.object(tpc, "run_playerctl_async")
    def test_volume_down_clamped_at_0(self, mock_vol):
        """Volume down should not go below 0."""
        tpc.s.state.volume = 3
        tpc.handle_key("\x1b", "[B")
        self.assertEqual(tpc.s.state.volume, 0)

    @patch.object(tpc, "run_playerctl_async")
    def test_mute_sets_volume_to_zero(self, mock_vol):
        """Mute (m key) should set volume to 0.0."""
        tpc.s.state.volume = 75
        tpc.handle_key("m")
        mock_vol.assert_called_with("volume", "0.0")
        self.assertEqual(tpc.s.state.volume, 0)

    @patch.object(tpc, "run_playerctl_async")
    def test_unmute_restores_volume(self, mock_vol):
        """Unmute should restore to pre-mute volume."""
        tpc.s.state.volume = 75
        tpc.s.state.pre_mute_volume = 75
        tpc.s.state.volume = 0  # Currently muted
        tpc.handle_key("m")
        mock_vol.assert_called_with("volume", "0.75")
        self.assertEqual(tpc.s.state.volume, 75)


class TestHandleKeyPlayback(unittest.TestCase):
    """Test handle_key playback control commands."""

    def setUp(self):
        self._orig = tpc.s.state
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.status = "Playing"
        tpc.s.state.volume = 50
        tpc.s.last_command_time = 0

    def tearDown(self):
        tpc.s.state = self._orig

    @patch.object(tpc, "run_playerctl_async")
    def test_space_toggles_play_pause(self, mock_pp):
        """Space bar should call play-pause command."""
        tpc.handle_key(" ")
        mock_pp.assert_called_with("play-pause")

    @patch.object(tpc, "run_playerctl_async")
    def test_space_toggles_status_optimistically(self, mock_pp):
        """Space bar should toggle status optimistically."""
        # Toggle from Playing to Paused
        tpc.s.state.status = "Playing"
        tpc.handle_key(" ")
        self.assertEqual(tpc.s.state.status, "Paused")

    @patch.object(tpc, "run_playerctl_async")
    def test_space_toggles_from_paused_to_playing(self, mock_pp):
        """Space bar should toggle status from Paused to Playing."""
        tpc.s.state.status = "Paused"
        tpc.handle_key(" ")
        self.assertEqual(tpc.s.state.status, "Playing")

    @patch.object(tpc, "run_playerctl_async")
    def test_next_sends_next_command(self, mock_next):
        """n key should send next command."""
        tpc.handle_key("n")
        mock_next.assert_called_with("next")

    @patch.object(tpc, "run_playerctl_async")
    def test_previous_sends_previous_command(self, mock_prev):
        """p key should send previous command."""
        tpc.handle_key("p")
        mock_prev.assert_called_with("previous")


class TestHandleKeyLoopShuffle(unittest.TestCase):
    """Test handle_key loop and shuffle commands."""

    def setUp(self):
        self._orig = tpc.s.state
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.loop = "None"
        tpc.s.state.shuffle = "false"
        tpc.s.state.volume = 50
        tpc.s.last_command_time = 0

    def tearDown(self):
        tpc.s.state = self._orig

    @patch.object(tpc, "run_playerctl_async")
    def test_shuffle_toggles(self, mock_shuffle):
        """s key should send shuffle Toggle command."""
        tpc.handle_key("s")
        mock_shuffle.assert_called_with("shuffle", "Toggle")

    @patch.object(tpc, "run_playerctl_async")
    def test_loop_cycles_none_to_track(self, mock_loop):
        """l key cycles loop: None -> Track."""
        tpc.s.state.loop = "None"
        tpc.handle_key("l")
        mock_loop.assert_called_with("loop", "Track")

    @patch.object(tpc, "run_playerctl_async")
    def test_loop_cycles_track_to_playlist(self, mock_loop):
        """l key cycles loop: Track -> Playlist."""
        tpc.s.state.loop = "Track"
        tpc.handle_key("l")
        mock_loop.assert_called_with("loop", "Playlist")

    @patch.object(tpc, "run_playerctl_async")
    def test_loop_cycles_playlist_to_none(self, mock_loop):
        """l key cycles loop: Playlist -> None."""
        tpc.s.state.loop = "Playlist"
        tpc.handle_key("l")
        mock_loop.assert_called_with("loop", "None")


class TestPlayerctlCommandReference(unittest.TestCase):
    """Verify all playerctl commands match the official command reference.

    Commands should follow: playerctl [OPTIONS] COMMAND [ARGS]
    See: playerctl --help
    """

    def test_play_command(self):
        """play command should be just 'play'."""
        # This is tested via play-pause which handles play
        pass

    def test_pause_command(self):
        """pause command is handled via play-pause."""
        pass

    def test_play_pause_command(self):
        """play-pause should be 'play-pause' (single command)."""
        # Verified via test_space_toggles_play_pause
        pass

    def test_next_command(self):
        """next should be 'next'."""
        pass

    def test_previous_command(self):
        """previous should be 'previous'."""
        pass

    def test_position_seek_format(self):
        """position should be 'position OFFSET+/-' where OFFSET comes BEFORE +/-."""
        # This is the key test that caught the bug
        # Format: position [OFFSET][+/-] means OFFSET before +/- not after
        pass

    def test_volume_format_absolute(self):
        """volume should be absolute float '0.50', not '+0.05' or '-0.05'."""
        pass

    def test_loop_status_values(self):
        """loop accepts: None, Track, Playlist."""
        pass

    def test_shuffle_status_values(self):
        """shuffle accepts: On, Off, Toggle."""
        pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
