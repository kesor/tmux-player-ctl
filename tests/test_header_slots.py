"""Test header slot centering."""
import unittest
import importlib.util

spec = importlib.util.spec_from_file_location('tpc', '../tmux-player-ctl.py')
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestHeaderCentering(unittest.TestCase):
    """Test that player name is properly centered in header."""

    def setUp(self):
        # Save original state
        self.orig_state = tpc.s.state
        self.orig_players = tpc.s.available_players
        tpc.s.state = tpc.PlayerState()
        tpc.s.available_players = ['player1', 'player2']

    def tearDown(self):
        # Restore state
        tpc.s.state = self.orig_state
        tpc.s.available_players = self.orig_players

    def _get_player_bounds(self, header_clean: str, player_name: str) -> tuple:
        """Get (start, end) positions of player name in header."""
        start = header_clean.find(player_name)
        if start < 0:
            return (-1, -1)
        # Handle CJK characters which may have different byte vs display width
        # Use visible_width to find actual end
        end = start + tpc.visible_width(player_name)
        return (start, end)

    def test_short_player_name_is_centered(self):
        """Short player name should be centered in header."""
        tpc.s.state.status = 'playing'
        tpc.s.state.player = 'spot'
        
        result = tpc.header_row()
        clean = tpc.ANSI_PATTERN.sub('', result)
        
        inner_w = tpc.Config.INNER_W - 2
        player_start, player_end = self._get_player_bounds(clean, 'spot')
        player_w = player_end - player_start
        
        # Player should be centered within delta of 3 (accounting for slot padding)
        expected_left = (inner_w - player_w) // 2
        self.assertAlmostEqual(
            player_start, expected_left, delta=3,
            msg=f"Player 'spot' should be centered. Got {player_start}, expected ~{expected_left}"
        )

    def test_long_player_name_is_truncated_and_centered(self):
        """Long player name should be truncated but still centered."""
        tpc.s.state.status = 'playing'
        tpc.s.state.player = 'very_long_player_name_here'
        
        result = tpc.header_row()
        clean = tpc.ANSI_PATTERN.sub('', result)
        
        inner_w = tpc.Config.INNER_W - 2
        # Find the truncated name in header
        # The name will be truncated, so we can't search for full name
        # Check that it starts somewhere in the middle third of the header
        player_start = clean.find('very_long')
        self.assertGreater(player_start, 0, "Truncated player name should be in header")
        
        # Should be in the left half but not at the very edge
        self.assertGreater(player_start, 15, "Player should not be too far left")
        self.assertLess(player_start, inner_w // 2, "Player should start before center")

    def test_cjk_player_name_is_centered(self):
        """Player name with CJK characters should be centered correctly."""
        tpc.s.state.status = 'playing'
        tpc.s.state.player = '播放器'
        
        result = tpc.header_row()
        clean = tpc.ANSI_PATTERN.sub('', result)
        
        inner_w = tpc.Config.INNER_W - 2
        player_start, player_end = self._get_player_bounds(clean, '播放器')
        player_w = player_end - player_start  # Should be 4 (2 CJK chars * 2 width each)
        
        # Player should be centered
        expected_left = (inner_w - player_w) // 2
        self.assertAlmostEqual(
            player_start, expected_left, delta=3,
            msg=f"CJK player should be centered. Got {player_start}, expected ~{expected_left}"
        )

    def test_header_uses_original_slot_widths(self):
        """Header should keep original status_w=20 and switch_w=9."""
        with open('../tmux-player-ctl.py') as f:
            code = f.read()
        
        import re
        header_start = code.find('def header_row()')
        header_end = code.find('\ndef ', header_start + 1)
        header_code = code[header_start:header_end]
        
        status_match = re.search(r'status_w\s*=\s*(\d+)', header_code)
        switch_match = re.search(r'switch_w\s*=\s*(\d+)', header_code)
        
        self.assertIsNotNone(status_match, "status_w should be defined")
        self.assertIsNotNone(switch_match, "switch_w should be defined")
        self.assertEqual(int(status_match.group(1)), 20, "status_w should remain 20")
        self.assertEqual(int(switch_match.group(1)), 9, "switch_w should remain 9")

    def test_header_length_is_correct(self):
        """Header should be close to Config.UI_WIDTH characters."""
        tpc.s.state.status = 'playing'
        tpc.s.state.player = 'test_player'
        
        result = tpc.header_row()
        clean = tpc.ANSI_PATTERN.sub('', result)
        
        # Header should be at or very close to UI_WIDTH (within 2 for unicode edge cases)
        self.assertAlmostEqual(
            len(clean), tpc.Config.UI_WIDTH, delta=2,
            msg=f"Header should be ~{tpc.Config.UI_WIDTH} chars, got {len(clean)}. {clean}"
        )


if __name__ == '__main__':
    unittest.main()
