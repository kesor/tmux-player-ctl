"""Tests for metadata stream buffering (Bug #1 from code review).

Ensures complete metadata blocks are parsed even when split across chunks.
The buffering strategy: only extract blocks when we see TWO complete blocks,
ensuring we never extract a partial block.
"""

import unittest
from unittest.mock import patch, MagicMock

import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestMetadataBuffering(unittest.TestCase):
    """Bug #1: Metadata Stream Parsing is Not Chunk-Safe.
    
    The main loop reads follower output via os.read(4096), but pipes deliver
    data in arbitrary chunks. A read can split mid-UTF-8 character, mid-field,
    or between updates. We need a persistent buffer and parse only complete
    logical records.
    """

    def setUp(self):
        """Reset PlayerTracker state before each test."""
        tpc.s._meta_buf = ""
        tpc.s.state = tpc.PlayerState()

    def tearDown(self):
        """Cleanup after test."""
        tpc.s._meta_buf = ""

    def test_player_tracker_has_meta_buf(self):
        """PlayerTracker should have a _meta_buf attribute."""
        self.assertTrue(hasattr(tpc.PlayerTracker, '_meta_buf'))

    def test_meta_buf_initialized_empty(self):
        """_meta_buf should be empty on initialization."""
        tracker = tpc.PlayerTracker()
        self.assertEqual(tracker._meta_buf, "")


class TestExtractCompleteBlocks(unittest.TestCase):
    """Test extracting complete metadata blocks from buffered data."""

    def setUp(self):
        tpc.s._meta_buf = ""
        tpc.s.state = tpc.PlayerState()

    def tearDown(self):
        tpc.s._meta_buf = ""

    def test_single_block_stays_in_buffer(self):
        """A single block should stay in buffer (ambiguous - may be partial)."""
        data = '\n@0@spotify\n@1@Playing\n@2@Song Title'
        complete = tpc._extract_complete_metadata_blocks(data)
        # No blocks extracted - single block is ambiguous
        self.assertEqual(len(complete), 0)
        # Data is in buffer
        self.assertIn('@0@spotify', tpc.s._meta_buf)

    def test_two_blocks_extracts_first(self):
        """Two complete blocks should extract the first (complete) one."""
        data = '\n@0@spotify\n@1@Playing\n@2@Song1\n@0@spotify\n@1@Paused\n@2@Song2'
        complete = tpc._extract_complete_metadata_blocks(data)
        self.assertEqual(len(complete), 1)
        self.assertIn('@2@Song1', complete[0])
        self.assertNotIn('Song2', complete[0])

    def test_three_blocks_extracts_first_two(self):
        """Three complete blocks should extract the first two."""
        data = '\n@0@spotify\n@1@Playing\n@2@Song1\n@0@spotify\n@1@Paused\n@2@Song2\n@0@spotify\n@1@Stopped\n@2@Song3'
        complete = tpc._extract_complete_metadata_blocks(data)
        self.assertEqual(len(complete), 2)
        self.assertIn('Song1', complete[0])
        self.assertIn('Song2', complete[1])
        # Third block should be in buffer
        self.assertIn('@2@Song3', tpc.s._meta_buf)

    def test_partial_block_remains_in_buffer(self):
        """A partial block (no second block marker) should remain in buffer."""
        data = '\n@0@spotify\n@1@Playing'
        complete = tpc._extract_complete_metadata_blocks(data)
        self.assertEqual(len(complete), 0)
        self.assertIn('@0@spotify', tpc.s._meta_buf)

    def test_block_without_leading_newline_stays_in_buffer(self):
        """Block starting with @0@ (no leading newline) should stay in buffer."""
        data = '@0@spotify\n@1@Playing\n@2@Song'
        complete = tpc._extract_complete_metadata_blocks(data)
        self.assertEqual(len(complete), 0)
        self.assertIn('@0@spotify', tpc.s._meta_buf)

    def test_empty_data_does_not_crash(self):
        """Empty data should not crash."""
        result = tpc._extract_complete_metadata_blocks("")
        self.assertEqual(result, [])

    def test_garbage_at_start_is_discarded(self):
        """Garbage before \n@0@ should be discarded."""
        data = 'some garbage\n@0@spotify\n@1@Playing\n@2@Song'
        complete = tpc._extract_complete_metadata_blocks(data)
        # The block should not include garbage
        self.assertEqual(len(complete), 0)
        self.assertIn('@0@spotify', tpc.s._meta_buf)
        self.assertNotIn('garbage', tpc.s._meta_buf)


class TestChunkSplitting(unittest.TestCase):
    """Test handling of data split across multiple chunks."""

    def setUp(self):
        tpc.s._meta_buf = ""
        tpc.s.state = tpc.PlayerState()

    def tearDown(self):
        tpc.s._meta_buf = ""

    def test_split_field_value_reassembled(self):
        """A field value split across chunks should be reassembled."""
        # Chunk 1: split in middle of artist name
        chunk1 = '\n@0@spotify\n@1@Playing\n@3@Beeth'
        complete1 = tpc._extract_complete_metadata_blocks(chunk1)
        self.assertEqual(len(complete1), 0)
        
        # Chunk 2: completes the field and has the next block
        chunk2 = 'oven Symphony\n@0@spotify'
        complete2 = tpc._extract_complete_metadata_blocks(chunk2)
        self.assertEqual(len(complete2), 1)
        # The block should have the complete reassembled artist name
        self.assertIn('Beethoven Symphony', complete2[0])

    def test_split_at_field_boundary(self):
        """Split at field boundary should work correctly."""
        chunk1 = '\n@0@spotify\n@1@Playing\n@2@Song Title'
        chunk2 = '\n@0@spotify\n@1@Paused\n@2@Next Song'
        
        tpc._extract_complete_metadata_blocks(chunk1)
        complete2 = tpc._extract_complete_metadata_blocks(chunk2)
        
        self.assertEqual(len(complete2), 1)
        self.assertIn('Song Title', complete2[0])

    def test_multiple_chunks_accumulate(self):
        """Multiple chunks should accumulate in buffer."""
        chunk1 = '\n@0@spotify'
        chunk2 = '\n@1@Playing'
        chunk3 = '\n@2@Song'
        
        tpc._extract_complete_metadata_blocks(chunk1)
        tpc._extract_complete_metadata_blocks(chunk2)
        tpc._extract_complete_metadata_blocks(chunk3)
        
        # All parts should be in buffer
        self.assertIn('@0@spotify', tpc.s._meta_buf)
        self.assertIn('@1@Playing', tpc.s._meta_buf)
        self.assertIn('@2@Song', tpc.s._meta_buf)

    def test_split_at_4096_boundary(self):
        """Simulate split at 4096 byte boundary - large chunks accumulate."""
        # Simulate arbitrary byte split - the split happens in the middle of a field
        # First chunk: has first block
        chunk1 = '\n@0@spotify\n@1@Playing\n@2@Long Song Title That Was Split'
        # Second chunk: has second and third blocks
        chunk2 = '\n@0@spotify\n@1@Paused\n@2@Second Song\n@0@spotify\n@1@Stopped\n@2@Third Song'
        
        tpc._extract_complete_metadata_blocks(chunk1)
        complete2 = tpc._extract_complete_metadata_blocks(chunk2)
        
        # Should extract blocks when we have 2+ complete blocks
        self.assertGreaterEqual(len(complete2), 1)
        # The key is that partial data is handled correctly - no crashes


class TestIntegrationWithParseMetadata(unittest.TestCase):
    """Test that extracted blocks parse correctly."""

    def setUp(self):
        tpc.s._meta_buf = ""
        tpc.s.state = tpc.PlayerState()
        tpc.s.state.player = "spotify"

    def tearDown(self):
        tpc.s._meta_buf = ""

    def test_extracted_block_parses_correctly(self):
        """Complete block extracted from buffer should parse correctly."""
        raw = '\n@0@spotify\n@1@Playing\n@2@Test Song\n@3@Test Artist'
        complete = tpc._extract_complete_metadata_blocks(raw)
        # Add another block to trigger extraction
        raw2 = '\n@0@spotify\n@1@Paused\n@2@Next'
        complete2 = tpc._extract_complete_metadata_blocks(raw2)
        
        self.assertEqual(len(complete2), 1)
        parsed = tpc.parse_metadata(complete2[0])
        self.assertEqual(parsed.get('player'), 'spotify')
        self.assertEqual(parsed.get('status'), 'Playing')
        self.assertEqual(parsed.get('title'), 'Test Song')
        self.assertEqual(parsed.get('artist'), 'Test Artist')


if __name__ == "__main__":
    unittest.main(verbosity=2)
