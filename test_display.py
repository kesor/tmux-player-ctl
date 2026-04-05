#!/usr/bin/env python3
"""Simple display test for progress and volume rows."""

import importlib.util

spec = importlib.util.spec_from_file_location("tpc", "./tmux-player-ctl.py")
tpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpc)

# Simulate multiple players available so switch tool shows
tpc.s.available_players = ["spotifyd", "firefox"]

# Ruler
print("1234567890" * 10)
tpc.s.state.position = 45
tpc.s.state.length = 140
tpc.s.state.volume = 89
tpc.s.state.player = "spotifyd"
tpc.s.state.status = "Playing"
tpc.s.state.shuffle = "true"
# tpc.s.state.loop = "false"
tpc.s.state.title = "Mission Select"
tpc.s.state.artist = "Matthew S Burns"
tpc.s.state.album = "Möbius Front '83 (Original Soundtrack)"
print(tpc.border_top())
print(tpc.header_row())
print(tpc.border_mid())
print(tpc.album_row())
print(tpc.track_row())
print(tpc.artist_row())
print(tpc.border_mid())
print(tpc.progress_row())
print(tpc.volume_row())
print(tpc.border_mid())
print(tpc.toolbar_row())
print(tpc.border_bot())
