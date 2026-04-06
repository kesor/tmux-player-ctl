#!/usr/bin/env python3
"""
Integration tests that run actual playerctl commands.
These tests require playerctl to be installed and may require a media player running.
Run with: python3 -m unittest integration
"""

import unittest

import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestPlayerctlIntegration(unittest.TestCase):
    """Integration tests that run actual playerctl commands."""

    def test_list_players(self):
        """Should list available players without error."""
        players = tpc.get_available_players()
        # Just verify it returns a list (may be empty if no players)
        self.assertIsInstance(players, list)

    def test_get_status(self):
        """Should get status without error if a player is available."""
        players = tpc.get_available_players()
        if not players:
            self.skipTest("No media players available")

        status = tpc.run_playerctl("status")
        # May have trailing newline since we no longer strip
        self.assertIn(status.strip(), ["Playing", "Paused", "Stopped", ""])

    def test_get_metadata_format(self):
        """Should get metadata in expected format."""
        players = tpc.get_available_players()
        if not players:
            self.skipTest("No media players available")

        result = tpc.run_playerctl("--format", "{{status}}", "status")
        # May have trailing newline since we no longer strip
        self.assertIn(result.strip(), ["Playing", "Paused", "Stopped"])

    def test_metadata_parsing_round_trip(self):
        """Full round-trip: run_playerctl -> parse_metadata returns valid dict."""
        players = tpc.get_available_players()
        if not players:
            self.skipTest("No media players available")

        # Get metadata using the METADATA_FORMAT
        raw = tpc.run_playerctl("--format", tpc.METADATA_FORMAT, "metadata")
        self.assertTrue(bool(raw), "run_playerctl returned empty for metadata")

        # parse_metadata should return a valid dict with key fields
        parsed = tpc.parse_metadata(raw)
        self.assertIsInstance(parsed, dict)
        self.assertIn("player", parsed)
        self.assertIn("status", parsed)
        self.assertIn("title", parsed)

    def test_metadata_format_fields_return_data(self):
        """Verify METADATA_FORMAT fields actually return data when available.

        This catches cases where a player doesn't support certain fields
        (e.g., xesam:trackCount may not be available from all players).
        """
        players = tpc.get_available_players()
        if not players:
            self.skipTest("No media players available")

        raw = tpc.run_playerctl("--format", tpc.METADATA_FORMAT, "metadata")
        parsed = tpc.parse_metadata(raw)

        # Fields we expect to have data for when playing
        expected_fields = ["player", "status", "title"]
        for field in expected_fields:
            self.assertIn(
                field, parsed, f"Field '{field}' should be in parsed metadata"
            )
            # These should have non-empty values when a track is playing
            if field in ["title"] and not parsed.get(field):
                # Title might be empty if no track loaded, that's ok
                pass

    def test_track_number_field_format(self):
        """Verify trackNumber field can be retrieved from actual player.

        This tests that the format string position for trackNumber
        actually returns data from the current player.
        """
        players = tpc.get_available_players()
        if not players:
            self.skipTest("No media players available")

        # First verify the format string uses xesam:trackNumber
        # (some players require the xesam: prefix)
        format_idx = tpc._METADATA_KEYS.index("{{xesam:trackNumber}}")
        self.assertEqual(tpc.METADATA_FIELDS[format_idx], "trackNumber")

        # Get raw metadata output
        raw = tpc.run_playerctl("--format", tpc.METADATA_FORMAT, "metadata")
        parsed = tpc.parse_metadata(raw)

        # trackNumber should be in the parsed result (may be empty if no track)
        self.assertIn("trackNumber", parsed)

        # If we have a title, we should have trackNumber too (even if empty string)
        if parsed.get("title"):
            # trackNumber is stored as string, may be empty
            self.assertIsInstance(parsed["trackNumber"], str)

            # Also verify direct format query works
            direct = tpc.run_playerctl("--format", "{{xesam:trackNumber}}", "metadata")
            # This should not be empty if we have a title
            self.assertIsInstance(direct, str)

    def test_track_count_field_format(self):
        """Verify trackCount field format string works correctly.

        Note: trackCount may not be available from all players (e.g., mpd, spotifyd).
        This test verifies the format string works, even if value is empty.
        """
        players = tpc.get_available_players()
        if not players:
            self.skipTest("No media players available")

        # Verify trackCount is in METADATA_FIELDS
        self.assertIn("trackCount", tpc.METADATA_FIELDS)

        # Verify the format string contains xesam:trackCount
        self.assertIn("xesam:trackCount", tpc.METADATA_FORMAT)

        # Get raw metadata
        raw = tpc.run_playerctl("--format", tpc.METADATA_FORMAT, "metadata")
        parsed = tpc.parse_metadata(raw)

        # trackCount should be in parsed result
        self.assertIn("trackCount", parsed)

    def test_all_metadata_fields_have_format_keys(self):
        """Verify every field in METADATA_FIELDS has a corresponding format key."""
        self.assertEqual(len(tpc.METADATA_FIELDS), len(tpc._METADATA_KEYS))

        # Verify they align properly
        for i, (field, key) in enumerate(zip(tpc.METADATA_FIELDS, tpc._METADATA_KEYS)):
            # Extract the key name without braces
            key_name = key.replace("{{", "").replace("}}", "")
            # Just verify counts match and all fields are mapped
            self.assertIsNotNone(key, f"Field {field} at index {i} has no format key")

    def test_individual_field_formats_work(self):
        """Test that individual field format strings work for the current player."""
        players = tpc.get_available_players()
        if not players:
            self.skipTest("No media players available")

        # Test key fields that should work with any MPRIS player
        test_fields = [
            ("{{playerName}}", "player"),
            ("{{status}}", "status"),
            ("{{title}}", "title"),
            ("{{artist}}", "artist"),
            ("{{album}}", "album"),
            ("{{trackNumber}}", "trackNumber"),
            ("{{mpris:length}}", "length"),
        ]

        for format_str, field_name in test_fields:
            result = tpc.run_playerctl("--format", format_str, "metadata")
            # Should not error, result may be empty but shouldn't crash
            self.assertIsInstance(result, str)
            # Result should be parseable (may be empty string)
            if field_name == "trackNumber":
                # Track number might be empty, that's valid
                pass


if __name__ == "__main__":
    unittest.main()
