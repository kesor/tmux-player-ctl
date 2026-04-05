"""Test truncate function with CJK boundary handling."""
import unittest
import importlib.util

spec = importlib.util.spec_from_file_location('tpc', '../tmux-player-ctl.py')
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestTruncateCJK(unittest.TestCase):
    """Test truncate handles CJK boundaries correctly."""

    def test_truncate_pure_ascii(self):
        """ASCII text truncates with single ellipsis."""
        result = tpc.truncate("hello world", 5)
        self.assertEqual(result, "hello…")

    def test_truncate_cjk_exact_fit(self):
        """CJK text that exactly fits doesn't get ellipsis."""
        result = tpc.truncate("日本", 4)
        self.assertEqual(result, "日本")

    def test_truncate_cjk_one_char(self):
        """CJK truncated to one char gets double ellipsis (CJK boundary)."""
        result = tpc.truncate("日本", 1)
        self.assertEqual(result, "……")

    def test_truncate_cjk_boundary(self):
        """CJK at boundary (2 chars, width 3) gets double ellipsis."""
        result = tpc.truncate("日本", 3)
        self.assertEqual(result, "日……")

    def test_truncate_mixed_ascii_cjk(self):
        """Mixed ASCII and CJK text truncates with ellipsis."""
        result = tpc.truncate("日本america", 6)
        # 日本 = 4, am = 2, total = 6, fits. Adds ellipsis for total 7 visible
        self.assertEqual(result, "日本am…")

    def test_truncate_cjk_only_long(self):
        """Long CJK-only text truncates at CJK boundary."""
        result = tpc.truncate("日本日本語中文한국어", 10)
        # 日本日本 = 8, can't fit 日 (CJK boundary)
        self.assertEqual(result, "日本日本語……")

    def test_truncate_width_one_ascii(self):
        """ASCII truncated to width 1 gets single ellipsis."""
        result = tpc.truncate("hello", 1)
        self.assertEqual(result, "h…")


class TestHeaderRowWidth(unittest.TestCase):
    """Test header_row produces correct widths."""

    def setUp(self):
        self.orig_state = tpc.s.state
        self.orig_players = tpc.s.available_players
        tpc.s.state = tpc.PlayerState()
        tpc.s.available_players = ['test', 'other']

    def tearDown(self):
        tpc.s.state = self.orig_state
        tpc.s.available_players = self.orig_players

    def test_header_width_recording_long_cjk(self):
        """Header with recording status and long CJK player name has correct width."""
        tpc.s.state.player = 'spotifyd旅ロ京青利セムレ弱改フヨス波府かばぼ意送でぼ調掲察たス日西重ケアナ住橋ユムミク順待ふかんぼ人奨貯鏡すびそ。'
        tpc.s.state.status = 'recording'
        
        result = tpc.header_row()
        clean = tpc.ANSI_PATTERN.sub('', result)
        vw = tpc.visible_width(clean)
        
        self.assertEqual(vw, tpc.Config.UI_WIDTH, 
            f"Header should be {tpc.Config.UI_WIDTH}, got {vw}. '{clean}'")

    def test_header_width_single_player(self):
        """Header with single player has correct width."""
        tpc.s.available_players = ['test']
        tpc.s.state.player = 'test'
        tpc.s.state.status = 'playing'
        
        result = tpc.header_row()
        clean = tpc.ANSI_PATTERN.sub('', result)
        vw = tpc.visible_width(clean)
        
        self.assertEqual(vw, tpc.Config.UI_WIDTH,
            f"Header should be {tpc.Config.UI_WIDTH}, got {vw}. '{clean}'")

    def test_header_width_empty(self):
        """Empty header has correct width."""
        tpc.s.state.player = ''
        tpc.s.state.status = ''
        tpc.s.available_players = []
        
        result = tpc.header_row()
        clean = tpc.ANSI_PATTERN.sub('', result)
        vw = tpc.visible_width(clean)
        
        self.assertEqual(vw, tpc.Config.UI_WIDTH,
            f"Header should be {tpc.Config.UI_WIDTH}, got {vw}. '{clean}'")


if __name__ == '__main__':
    unittest.main()
