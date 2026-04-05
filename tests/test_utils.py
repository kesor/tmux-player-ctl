"""Utility function tests: status_color, format_player_name, player_args, playerctl subprocess, quit keys, get_best_player, reset_state."""

import unittest
from unittest.mock import patch, MagicMock

import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestStatusColor(unittest.TestCase):
    """Test status_color() returns correct colors."""

    def test_playing_returns_green(self):
        """Playing status should return green color."""
        result = tpc.status_color("Playing")
        self.assertEqual(result, tpc.Theme.PLAYING)

    def test_paused_returns_yellow(self):
        """Paused status should return yellow color."""
        result = tpc.status_color("Paused")
        self.assertEqual(result, tpc.Theme.PAUSED)

    def test_stopped_returns_overlay0(self):
        """Stopped status should return dim color."""
        result = tpc.status_color("Stopped")
        self.assertEqual(result, tpc.Theme.STOPPED)

    def test_recording_returns_red(self):
        """Recording status should return red color."""
        result = tpc.status_color("Recording")
        self.assertEqual(result, tpc.Theme.RECORDING)

    def test_unknown_returns_stopped(self):
        """Unknown status should return stopped color."""
        result = tpc.status_color("Unknown")
        self.assertEqual(result, tpc.Theme.STOPPED)


class TestFormatPlayerName(unittest.TestCase):
    """Test _format_player_name() - formats player name for display."""

    def test_simple_name(self):
        """Simple name is preserved."""
        result = tpc._format_player_name("spotify")
        self.assertEqual(result, "spotify")

    def test_with_instance(self):
        """Name with instance is shortened."""
        result = tpc._format_player_name("spotify.instance123")
        self.assertEqual(result, "spotify")

    def test_empty_name(self):
        """Empty name returns empty string."""
        result = tpc._format_player_name("")
        self.assertEqual(result, "")


class TestPlayerArgs(unittest.TestCase):
    """Test player_args() - returns playerctl arguments."""

    def setUp(self):
        self._orig = tpc.s.current_player
        tpc.s.current_player = ""

    def tearDown(self):
        tpc.s.current_player = self._orig

    def test_no_player_returns_empty(self):
        """No player returns empty list."""
        tpc.s.current_player = ""
        result = tpc.player_args()
        self.assertEqual(result, [])

    def test_with_player_returns_p_flag(self):
        """With player returns -p flag."""
        tpc.s.current_player = "spotify"
        result = tpc.player_args()
        self.assertEqual(result, ["-p", "spotify"])


class TestThemeBG(unittest.TestCase):
    """Test Theme.BG - background color from environment."""

    def test_theme_has_bg(self):
        """Theme should have BG attribute."""
        self.assertTrue(hasattr(tpc.Theme, "BG"))

    def test_theme_bg_default_empty(self):
        """Theme.BG default is empty string."""
        self.assertEqual(tpc.Theme.BG, "")


class TestPlayerctlSubprocess(unittest.TestCase):
    """Test _playerctl_subprocess - single subprocess spawner."""

    @patch.object(tpc, "_playerctl_subprocess")
    def test_returns_completed_process(self, mock_sub):
        """Should return a CompletedProcess result."""
        mock_sub.return_value = MagicMock(returncode=0, stdout="Playing", stderr="")
        result = tpc.run_playerctl("status")
        self.assertEqual(result, "Playing")
        mock_sub.assert_called_once()


class TestCheckPlayerctl(unittest.TestCase):
    """Test check_playerctl() - verifies playerctl command exists."""

    @patch.object(tpc, "_playerctl_subprocess")
    def test_playerctl_exists_ok(self, mock_sub):
        """When playerctl --version succeeds, no error."""
        mock_sub.return_value = MagicMock(returncode=0, stdout="playerctl 2.12.0")
        tpc.check_playerctl()  # Should not raise

    @patch.object(tpc, "_playerctl_subprocess")
    def test_playerctl_missing_exits(self, mock_sub):
        """When playerctl is missing, exits with error."""
        mock_sub.return_value = MagicMock(returncode=127, stdout="", stderr="")
        with self.assertRaises(SystemExit) as cm:
            tpc.check_playerctl()
        self.assertEqual(cm.exception.code, 1)


class TestHandleKeyQuit(unittest.TestCase):
    """Test handle_key quit keys set shutdown_requested."""

    def setUp(self):
        self._orig = tpc.shutdown_requested
        tpc.shutdown_requested = False
        tpc.s.last_command_time = 0

    def tearDown(self):
        tpc.shutdown_requested = self._orig

    def test_q_quits_with_flag(self):
        """Pressing q sets shutdown_requested without calling sys.exit."""
        tpc.handle_key("q", "")
        self.assertTrue(tpc.shutdown_requested)

    def test_esc_quits_with_flag(self):
        """Pressing Esc sets shutdown_requested without calling sys.exit."""
        tpc.handle_key("\x1b", "")
        self.assertTrue(tpc.shutdown_requested)


class TestGetBestPlayer(unittest.TestCase):
    """Test get_best_player() - selects Playing > Paused > first."""

    @patch.object(tpc, "run_playerctl")
    def test_returns_playing_player(self, mock_run):
        """Should return first Playing player."""
        mock_run.return_value = "Playing"
        result = tpc.get_best_player(["spotify", "firefox", "vlc"])
        self.assertEqual(result, "spotify")

    @patch.object(tpc, "run_playerctl")
    def test_returns_paused_when_no_playing(self, mock_run):
        """Should return first Paused player when no Playing found."""
        mock_run.return_value = "Paused"
        result = tpc.get_best_player(["spotify", "firefox"])
        self.assertEqual(result, "spotify")

    @patch.object(tpc, "run_playerctl")
    def test_returns_first_when_all_stopped(self, mock_run):
        """Should return first player when all are Stopped."""
        mock_run.return_value = "Stopped"
        result = tpc.get_best_player(["spotify", "vlc"])
        self.assertEqual(result, "spotify")

    def test_empty_list_returns_none(self):
        """Empty list returns None."""
        result = tpc.get_best_player([])
        self.assertIsNone(result)


class TestConfigNoBG(unittest.TestCase):
    """Test Config - BG should no longer be in Config."""

    def test_config_no_bg(self):
        """Config should not have BG attribute."""
        self.assertFalse(hasattr(tpc.Config, "BG"))


class TestResetState(unittest.TestCase):
    """Test that dead code has been removed."""

    def test_no_cursor_move_pattern(self):
        """CURSOR_MOVE_PATTERN should be removed (unused)."""
        self.assertFalse(hasattr(tpc, "CURSOR_MOVE_PATTERN"))


class TestResetStateFull(unittest.TestCase):
    """Test reset_state() - resets player state."""

    def setUp(self):
        self._orig = tpc.s.state
        tpc.s.state = tpc.PlayerState()

    def tearDown(self):
        tpc.s.state = self._orig

    def test_resets_title(self):
        """Should reset title to empty string."""
        tpc.s.state.title = "Old Title"
        tpc.reset_state()
        self.assertEqual(tpc.s.state.title, "")

    def test_resets_artist(self):
        """Should reset artist to empty string."""
        tpc.s.state.artist = "Old Artist"
        tpc.reset_state()
        self.assertEqual(tpc.s.state.artist, "")

    def test_resets_album(self):
        """Should reset album to empty string."""
        tpc.s.state.album = "Old Album"
        tpc.reset_state()
        self.assertEqual(tpc.s.state.album, "")

    def test_resets_position(self):
        """Should reset position to 0."""
        tpc.s.state.position = 100.0
        tpc.reset_state()
        self.assertEqual(tpc.s.state.position, 0.0)

    def test_resets_status(self):
        """Should reset status to 'No player'."""
        tpc.s.state.status = "Playing"
        tpc.reset_state()
        self.assertEqual(tpc.s.state.status, "No player")

    def test_sets_dirty_true(self):
        """Should set dirty to True."""
        tpc.s.state.dirty = False
        tpc.reset_state()
        self.assertTrue(tpc.s.state.dirty)

    def test_resets_pre_mute_volume(self):
        """Should reset pre_mute_volume to default (50)."""
        tpc.s.state.pre_mute_volume = 75
        tpc.reset_state()
        self.assertEqual(tpc.s.state.pre_mute_volume, 50)

    def test_uses_fresh_player_state(self):
        """reset_state() creates a fresh PlayerState to avoid stale fields."""
        tpc.s.state.title = "Old Title"
        tpc.s.state.pre_mute_volume = 75
        tpc.s.state.artist = "Old Artist"
        tpc.reset_state()
        # All fields should match fresh PlayerState defaults
        fresh = tpc.PlayerState()
        self.assertEqual(tpc.s.state.title, fresh.title)
        self.assertEqual(tpc.s.state.pre_mute_volume, fresh.pre_mute_volume)
        self.assertEqual(tpc.s.state.artist, fresh.artist)
        self.assertEqual(tpc.s.state.status, "No player")


if __name__ == "__main__":
    unittest.main(verbosity=2)
