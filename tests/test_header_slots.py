"""Test header slot centering."""

import unittest
import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestHeaderCentering(unittest.TestCase):
    """Test that player name is properly centered in header."""

    def setUp(self):
        # Save original state
        self.orig_state = tpc.s.state
        self.orig_players = tpc.s.available_players
        tpc.s.state = tpc.PlayerState()
        tpc.s.available_players = ["player1", "player2"]

    def tearDown(self):
        # Restore state
        tpc.s.state = self.orig_state
        tpc.s.available_players = self.orig_players

    def test_short_player_name_has_more_left_padding_than_long(self):
        """Short player names get more left padding (centered), long names get less."""
        tpc.s.state.status = "playing"

        # Short name
        tpc.s.state.player = "spot"
        short_result = tpc.header_row()
        short_clean = tpc.ANSI_PATTERN.sub("", short_result)
        short_pos = short_clean.find("spot")

        # Long name
        tpc.s.state.player = "very_long_player_name"
        long_result = tpc.header_row()
        long_clean = tpc.ANSI_PATTERN.sub("", long_result)
        long_pos = long_clean.find("very_long")

        # Short name should have more left padding (start later) than long name
        self.assertGreater(
            short_pos,
            long_pos,
            f"Short name should be more centered (pos={short_pos}) than long (pos={long_pos})",
        )

    def test_long_player_name_is_truncated(self):
        """Long player name should be truncated with ellipsis."""
        tpc.s.state.status = "playing"
        tpc.s.state.player = "very_very_very_long_player_name_abc_def_ghi_jkl_mno"

        result = tpc.header_row()
        clean = tpc.ANSI_PATTERN.sub("", result)

        # Should have ellipsis where truncation happened
        self.assertIn("…", clean, f"Long name should be truncated. Header: {clean}")

    def test_cjk_player_name_gets_centered_padding(self):
        """CJK player name should get more padding than a long ASCII name."""
        tpc.s.state.status = "playing"

        # CJK name (short in characters but wide)
        tpc.s.state.player = "播放器"
        cjk_result = tpc.header_row()
        cjk_clean = tpc.ANSI_PATTERN.sub("", cjk_result)
        cjk_pos = cjk_clean.find("播放器")

        # Long ASCII name
        tpc.s.state.player = "very_long_player_name"
        long_result = tpc.header_row()
        long_clean = tpc.ANSI_PATTERN.sub("", long_result)
        long_pos = long_clean.find("very_long")

        # CJK name (4 visible width) should be more centered than long name
        self.assertGreater(
            cjk_pos,
            long_pos,
            f"CJK name should be more centered (pos={cjk_pos}) than long (pos={long_pos})",
        )

    def test_header_uses_switch_width_9(self):
        """Header switch width should use 9 characters."""
        with open("../tmux-player-ctl.py") as f:
            code = f.read()

        import re

        header_start = code.find("def header_row()")
        header_end = code.find("\ndef ", header_start + 1)
        header_code = code[header_start:header_end]

        # Check that switch_w is set to 9 when has_switch is true
        switch_match = re.search(r"switch_w\s*=\s*(\d+)", header_code)
        self.assertIsNotNone(switch_match, "switch_w should be defined")
        self.assertEqual(int(switch_match.group(1)), 9, "switch_w should remain 9")

    def test_header_length_is_correct(self):
        """Header should be close to Config.UI_WIDTH characters."""
        tpc.s.state.status = "playing"
        tpc.s.state.player = "test_player"

        result = tpc.header_row()
        clean = tpc.ANSI_PATTERN.sub("", result)

        # Header should be at or very close to UI_WIDTH (within 2 for unicode edge cases)
        self.assertAlmostEqual(
            len(clean),
            tpc.Config.UI_WIDTH,
            delta=2,
            msg=f"Header should be ~{tpc.Config.UI_WIDTH} chars, got {len(clean)}. {clean}",
        )


if __name__ == "__main__":
    unittest.main()
