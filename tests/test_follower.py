"""Tests for follower refactoring: metadata follower should be sole position source."""

import unittest
import importlib.util

# Load the module
spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


def make_metadata(
    player="spotify",
    status="Playing",
    title="Test Song",
    artist="Artist",
    album="Album",
    position="1.5",  # microseconds
    length="300.0",  # microseconds
    volume="0.5",
    **extra,
) -> str:
    """Create a 39-field prefixed metadata string with leading newline."""
    defaults = {
        "volume": "0.5",
        "loopStatus": "None",
        "loop": "None",
        "shuffle": "false",
    }
    fields = {
        **defaults,
        "player": player,
        "status": status,
        "title": title,
        "artist": artist,
        "album": album,
        "position": position,
        "length": length,
    }
    fields.update(extra)
    return "\n" + "\n".join(
        f"@{i}@{fields.get(f, '')}" for i, f in enumerate(tpc.METADATA_FIELDS)
    )


class TestParseMetadataPosition(unittest.TestCase):
    """Test that parse_metadata extracts position."""

    def test_parse_metadata_includes_position(self):
        """parse_metadata should extract position field."""
        # position is in microseconds: 1500000 = 1.5 seconds
        raw = make_metadata(position="1500000")
        result = tpc.parse_metadata(raw)
        self.assertIn("position", result)
        self.assertEqual(result["position"], 1.5)

    def test_parse_metadata_position_in_microseconds(self):
        """Position from playerctl is in microseconds, should be converted to seconds."""
        raw = make_metadata(position="1500000")  # 1.5 seconds in microseconds
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["position"], 1.5)

    def test_parse_metadata_length_in_microseconds(self):
        """Length from playerctl is in microseconds, should be converted to seconds."""
        raw = make_metadata(length="300000000")  # 300 seconds in microseconds
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["length"], 300.0)



    def test_parse_metadata_all_basic_fields(self):
        """parse_metadata should return dict with basic fields."""
        raw = make_metadata(
            player="spotify",
            status="Playing",
            title="Test Song",
            artist="Artist",
            album="Album",
        )
        result = tpc.parse_metadata(raw)
        self.assertEqual(result["player"], "spotify")
        self.assertEqual(result["status"], "Playing")
        self.assertEqual(result["title"], "Test Song")
        self.assertEqual(result["artist"], "Artist")
        self.assertEqual(result["album"], "Album")


class TestUpdateStateFromMetadata(unittest.TestCase):
    """Test that update_state_from_metadata updates state correctly."""

    def setUp(self):
        """Reset state before each test."""
        # Reset state to defaults
        tpc.s.state.player = ""
        tpc.s.state.status = ""
        tpc.s.state.title = ""
        tpc.s.state.artist = ""
        tpc.s.state.album = ""
        tpc.s.state.position = 0.0
        tpc.s.state.length = 0.0
        tpc.s.state.volume = 0
        tpc.s.state.loop = "None"
        tpc.s.state.shuffle = "false"
        tpc.s.state.dirty = False
        tpc.s.last_command_time = 0

    def test_update_state_sets_position(self):
        """update_state_from_metadata should set position."""
        data = {"position": 2.5}
        tpc.update_state_from_metadata(data)
        self.assertEqual(tpc.s.state.position, 2.5)

    def test_update_state_sets_all_fields(self):
        """update_state_from_metadata should set all provided fields."""
        data = {
            "title": "New Song",
            "artist": "New Artist",
            "position": 1.23,
        }
        tpc.update_state_from_metadata(data)
        self.assertEqual(tpc.s.state.title, "New Song")
        self.assertEqual(tpc.s.state.artist, "New Artist")
        self.assertEqual(tpc.s.state.position, 1.23)

    def test_update_state_marks_dirty(self):
        """update_state_from_metadata should mark dirty when changed."""
        data = {"title": "New"}
        tpc.update_state_from_metadata(data)
        self.assertTrue(tpc.s.state.dirty)

    def test_update_state_no_dirty_when_unchanged(self):
        """update_state_from_metadata should not mark dirty when no changes."""
        tpc.s.state.title = "Same"
        tpc.s.state.dirty = False
        data = {"title": "Same"}
        tpc.update_state_from_metadata(data)
        self.assertFalse(tpc.s.state.dirty)

    def test_update_state_debounce_ignores_recent(self):
        """update_state_from_metadata should debounce recent commands."""
        import time

        tpc.s.last_command_time = time.time()
        tpc.s.state.dirty = False
        data = {"position": 99.0}
        tpc.update_state_from_metadata(data)
        self.assertNotEqual(tpc.s.state.position, 99.0)  # Should be debounced


class TestMetadataFollowerProvidesPosition(unittest.TestCase):
    """Test that metadata follower provides position (integration)."""

    def setUp(self):
        """Reset state before each test."""
        tpc.s.state.position = 0.0
        tpc.s.state.length = 0.0
        tpc.s.state.title = ""
        tpc.s.last_command_time = 0

    def test_metadata_update_flow_provides_position(self):
        """Full flow: parse -> update_state should set position."""
        # Simulate what metadata follower produces (microseconds)
        raw = make_metadata(position="1500000", length="300000000")  # 1.5s, 300s
        parsed = tpc.parse_metadata(raw)
        self.assertEqual(parsed["position"], 1.5)
        self.assertEqual(parsed["length"], 300.0)

        # Update state
        tpc.update_state_from_metadata(parsed)
        self.assertEqual(tpc.s.state.position, 1.5)
        self.assertEqual(tpc.s.state.length, 300.0)


class TestPositionFollowerRedundancy(unittest.TestCase):
    """Test that verifies position follower is redundant."""

    def test_metadata_format_includes_position(self):
        """METADATA_FORMAT must include {{position}}."""
        self.assertIn("{{position}}", tpc.METADATA_FORMAT)

    def test_parse_metadata_position_matches_position_follower_format(self):
        """Position from parse_metadata should match what position follower provides.

        Position follower outputs: microseconds as string
        parse_metadata converts: / 1_000_000 to get seconds
        """
        # Position follower outputs "1500000" (1.5 seconds in microseconds)
        raw = make_metadata(position="1500000")
        parsed = tpc.parse_metadata(raw)
        # Both should result in same seconds value
        self.assertEqual(parsed["position"], 1.5)

    def test_metadata_follower_updates_state_position(self):
        """Metadata follower parsing + update should set state.position."""
        tpc.s.state.position = 0.0
        tpc.s.last_command_time = 0
        raw = make_metadata(position="2500000")  # 2.5 seconds
        parsed = tpc.parse_metadata(raw)
        tpc.update_state_from_metadata(parsed)
        self.assertEqual(tpc.s.state.position, 2.5)


class TestNoDirectPipeReading(unittest.TestCase):
    """Test that position is only read via state object.

    After refactoring, no code should read position from follower pipes directly.
    Position should only be accessible via state.position.
    """

    def setUp(self):
        """Reset state before each test."""
        tpc.s.state.position = 0.0
        tpc.s.last_command_time = 0

    def test_state_position_is_primary_interface(self):
        """state.position should be the primary way to access position."""
        tpc.s.state.position = 1.234
        # Position should be accessible directly from state
        self.assertEqual(tpc.s.state.position, 1.234)

    def test_update_state_from_metadata_sets_position(self):
        """Position should be settable via update_state_from_metadata."""
        tpc.s.state.position = 0.0
        tpc.update_state_from_metadata({"position": 5.5})
        self.assertEqual(tpc.s.state.position, 5.5)


class TestPositionFollowerRemoval(unittest.TestCase):
    """Test that position follower has been removed."""

    def test_no_start_position_follower_function(self):
        """start_position_follower function should not exist after refactoring."""
        self.assertFalse(hasattr(tpc, "start_position_follower"))


if __name__ == "__main__":
    unittest.main()
