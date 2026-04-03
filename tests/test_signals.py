#!/usr/bin/env python3
"""
Test suite for signal handling and cleanup functions.
"""

import unittest
import subprocess
import signal
from unittest.mock import patch, MagicMock

import importlib.util
spec = importlib.util.spec_from_file_location("tpc", "../tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)


class TestCleanupProc(unittest.TestCase):
    """Test cleanup_proc() kills processes correctly."""

    def test_does_nothing_if_proc_is_none(self):
        """Should not fail if proc is None."""
        # Should not raise
        tpc.cleanup_proc(None)

    def test_does_nothing_if_proc_already_dead(self):
        """Should not fail if proc has already terminated."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1  # Already dead
        
        tpc.cleanup_proc(mock_proc)
        
        mock_proc.terminate.assert_not_called()

    def test_terminates_running_process(self):
        """Should terminate process if it's still running."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # Still running
        
        tpc.cleanup_proc(mock_proc)
        
        mock_proc.terminate.assert_called_once()

    def test_kills_process_if_terminate_times_out(self):
        """Should kill process if terminate times out."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.wait.side_effect = subprocess.TimeoutExpired("cmd", 1)
        
        tpc.cleanup_proc(mock_proc)
        
        mock_proc.kill.assert_called_once()


class TestSetupSignals(unittest.TestCase):
    """Test setup_signals() registers handlers."""

    @patch("signal.signal")
    def test_registers_sigterm_handler(self, mock_signal):
        """Should register SIGTERM handler."""
        tpc.setup_signals()
        
        mock_signal.assert_any_call(signal.SIGTERM, tpc.request_shutdown)

    @patch("signal.signal")
    def test_registers_sigint_handler(self, mock_signal):
        """Should register SIGINT handler."""
        tpc.setup_signals()
        
        mock_signal.assert_any_call(signal.SIGINT, tpc.request_shutdown)

    @patch("signal.signal")
    def test_registers_sighup_handler(self, mock_signal):
        """Should register SIGHUP handler."""
        tpc.setup_signals()
        
        mock_signal.assert_any_call(signal.SIGHUP, tpc.request_shutdown)


if __name__ == "__main__":
    unittest.main()
