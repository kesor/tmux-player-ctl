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
        tpc.read_metadata_from_follower(raw)
        self.assertEqual(tpc.s.state.title, "Song")
        self.assertEqual(tpc.s.state.status, "Playing")

    def test_handles_embedded_newlines_in_value(self):
        """Fields with embedded newlines should be preserved."""
        # artist has newline in value
        raw = (
            "\n@0@spotify\n@1@Playing\n@2@Test\n@3@Multi\nLine\nArtist"
        )
        tpc.read_metadata_from_follower(raw)
        self.assertEqual(tpc.s.state.artist, "Multi\nLine\nArtist")

    def test_handles_partial_fields(self):
        """Player sends only non-empty fields - should still parse."""
        # Simulate player sending only fields 0-4
        raw = "\n@0@spotify\n@1@Playing\n@2@Test Song\n@3@Artist\n@4@Album"
        tpc.read_metadata_from_follower(raw)
        self.assertEqual(tpc.s.state.player, "")
        self.assertEqual(tpc.s.state.title, "Test Song")
        self.assertEqual(tpc.s.state.artist, "Artist")


if __name__ == "__main__":
    unittest.main(verbosity=2)
