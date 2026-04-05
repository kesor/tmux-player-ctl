"""Tests for metadata stream buffering (Bug #1 from code review).

Ensures complete metadata blocks are parsed even when split across chunks.
Strategy:
- First block is extracted immediately for fast initial display
- Subsequent blocks use conservative 2-block strategy
"""

import unittest
from unittest.mock import patch, MagicMock

import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestMetadataBuffering(unittest.TestCase):
    """Bug #1: Metadata Stream Parsing is Not Chunk-Safe."""

    def setUp(self):
        tpc.s._meta_buf = ""
        tpc.s._initial_state_shown = False
        tpc.s.state = tpc.PlayerState()

    def tearDown(self):
        tpc.s._meta_buf = ""
        tpc.s._initial_state_shown = False

    def test_player_tracker_has_meta_buf(self):
        """PlayerTracker should have a _meta_buf attribute."""
        self.assertTrue(hasattr(tpc.PlayerTracker, '_meta_buf'))

    def test_meta_buf_initialized_empty(self):
        """_meta_buf should be empty on initialization."""
        tracker = tpc.PlayerTracker()
        self.assertEqual(tracker._meta_buf, "")

    def test_initial_state_shown_flag_exists(self):
        """PlayerTracker should have _initial_state_shown flag."""
        self.assertTrue(hasattr(tpc.PlayerTracker, '_initial_state_shown'))


class TestExtractCompleteBlocks(unittest.TestCase):
    """Test extracting complete metadata blocks from buffered data."""

    def setUp(self):
        tpc.s._meta_buf = ""
        tpc.s._initial_state_shown = False
        tpc.s.state = tpc.PlayerState()

    def tearDown(self):
        tpc.s._meta_buf = ""
        tpc.s._initial_state_shown = False

    def test_single_block_extracted_when_empty(self):
        """First block is extracted immediately for fast initial display."""
        data = '\n@0@spotify\n@1@Playing\n@2@Song Title'
        complete = tpc._extract_complete_metadata_blocks(data)
        self.assertEqual(len(complete), 1)
        self.assertIn('@2@Song Title', complete[0])
        self.assertEqual(tpc.s._meta_buf, '')
        self.assertTrue(tpc.s._initial_state_shown)

    def test_second_single_block_stays_in_buffer(self):
        """After initial state, single blocks stay in buffer until next block arrives."""
        # First block - extracted immediately
        data1 = '\n@0@spotify\n@1@Playing\n@2@Song1'
        complete1 = tpc._extract_complete_metadata_blocks(data1)
        self.assertEqual(len(complete1), 1)
        
        # Second single block - stays in buffer (conservative)
        data2 = '\n@0@spotify\n@1@Paused\n@2@Song2'
        complete2 = tpc._extract_complete_metadata_blocks(data2)
        self.assertEqual(len(complete2), 0)  # Not extracted yet
        self.assertIn('@2@Song2', tpc.s._meta_buf)  # In buffer

    def test_two_blocks_extracts_first(self):
        """Two complete blocks extracts the first one."""
        data = '\n@0@spotify\n@1@Playing\n@2@Song1\n@0@spotify\n@1@Paused\n@2@Song2'
        complete = tpc._extract_complete_metadata_blocks(data)
        self.assertEqual(len(complete), 1)
        self.assertIn('@2@Song1', complete[0])

    def test_three_blocks_extracts_first_two(self):
        """Three complete blocks extracts the first two."""
        data = '\n@0@spotify\n@1@Playing\n@2@Song1\n@0@spotify\n@1@Paused\n@2@Song2\n@0@spotify\n@1@Stopped\n@2@Song3'
        complete = tpc._extract_complete_metadata_blocks(data)
        self.assertEqual(len(complete), 2)
        self.assertIn('Song1', complete[0])
        self.assertIn('Song2', complete[1])
        self.assertIn('@2@Song3', tpc.s._meta_buf)

    def test_empty_data_does_not_crash(self):
        """Empty data should not crash."""
        result = tpc._extract_complete_metadata_blocks("")
        self.assertEqual(result, [])


class TestChunkSplitting(unittest.TestCase):
    """Test handling of data split across multiple chunks."""

    def setUp(self):
        tpc.s._meta_buf = ""
        tpc.s._initial_state_shown = False
        tpc.s.state = tpc.PlayerState()

    def tearDown(self):
        tpc.s._meta_buf = ""
        tpc.s._initial_state_shown = False

    def test_split_field_in_single_read(self):
        """Field split across a single read is handled (partial stays)."""
        # This is one read with partial field
        data = '\n@0@spotify\n@1@Playing\n@3@Beeth'  # 'Beethoven' split
        complete = tpc._extract_complete_metadata_blocks(data)
        # First block extracted, partial field in buffer
        self.assertEqual(len(complete), 1)
        self.assertIn('@3@Beeth', complete[0])
        
        # Add more data to complete the field
        data2 = 'oven\n@0@spotify'  # completes Beethoven, starts new block
        complete2 = tpc._extract_complete_metadata_blocks(data2)
        self.assertEqual(len(complete2), 0)  # incomplete

    def test_subsequent_reads_extract_when_second_arrives(self):
        """After initial block, subsequent reads extract when next block arrives."""
        # First read - extracted immediately
        chunk1 = '\n@0@spotify\n@1@Playing\n@2@Song1'
        complete1 = tpc._extract_complete_metadata_blocks(chunk1)
        self.assertEqual(len(complete1), 1)
        
        # Second read - has partial block
        chunk2 = '\n@0@spotify\n@1@Paused\n@2@Song2'
        complete2 = tpc._extract_complete_metadata_blocks(chunk2)
        self.assertEqual(len(complete2), 0)  # Not extracted yet
        
        # Third read - completes the second block
        chunk3 = '\n@0@spotify\n@1@Stopped\n@2@Song3'
        complete3 = tpc._extract_complete_metadata_blocks(chunk3)
        # Should extract Song2 (the second block from chunk2)
        self.assertEqual(len(complete3), 1)
        self.assertIn('Song2', complete3[0])


class TestIntegrationWithParseMetadata(unittest.TestCase):
    """Test that extracted blocks parse correctly."""

    def setUp(self):
        tpc.s._meta_buf = ""
        tpc.s._initial_state_shown = False
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.player = "spotify"

    def tearDown(self):
        tpc.s._meta_buf = ""
        tpc.s._initial_state_shown = False

    def test_initial_block_parses_correctly(self):
        """First block parses correctly after extraction."""
        raw = '\n@0@spotify\n@1@Playing\n@2@Test Song\n@3@Test Artist'
        complete = tpc._extract_complete_metadata_blocks(raw)
        
        self.assertEqual(len(complete), 1)
        parsed = tpc.parse_metadata(complete[0])
        self.assertEqual(parsed.get('player'), 'spotify')
        self.assertEqual(parsed.get('status'), 'Playing')
        self.assertEqual(parsed.get('title'), 'Test Song')
        self.assertEqual(parsed.get('artist'), 'Test Artist')

    def test_second_block_extracted_when_third_arrives(self):
        """Second block extracted when third block arrives."""
        # First block - extracted immediately
        raw1 = '\n@0@spotify\n@1@Playing\n@2@Song1'
        complete1 = tpc._extract_complete_metadata_blocks(raw1)
        
        # Second block - not extracted yet
        raw2 = '\n@0@spotify\n@1@Paused\n@2@Song2'
        complete2 = tpc._extract_complete_metadata_blocks(raw2)
        self.assertEqual(len(complete2), 0)
        
        # Third block - triggers extraction of second
        raw3 = '\n@0@spotify\n@1@Stopped\n@2@Song3'
        complete3 = tpc._extract_complete_metadata_blocks(raw3)
        
        self.assertEqual(len(complete3), 1)
        parsed = tpc.parse_metadata(complete3[0])
        self.assertEqual(parsed.get('title'), 'Song2')


if __name__ == "__main__":
    unittest.main(verbosity=2)
