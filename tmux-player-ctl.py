#!/usr/bin/env python3
"""
tmux-player-ctl - A tmux popup controller for MPRIS media players via playerctl.

Usage:
    tmux display-popup -x0 -y0 -w100% -h100% -E "python3 /path/to/tmux-player-ctl.py"
"""

import os
import sys
import signal
import atexit
import subprocess
import select
import time
from dataclasses import dataclass
from typing import Optional, List


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

class Config:
    UI_WIDTH = 72          # Width of the UI box
    UI_HEIGHT = 12         # Number of rows in the UI
    SEEK_SECONDS = 10
    # Background: 24-bit RGB like "0;0;0" for black
    BG = os.environ.get("TPCTL_BG", "")  # e.g., "0;0;0" for black

# Player tracking
current_player: str = ""
available_players: List[str] = []
current_player_idx: int = -1

# ─────────────────────────────────────────────────────────────────────────────
# Icons
# ─────────────────────────────────────────────────────────────────────────────

# Unicode symbols (VS15 \uFE0E for text presentation)
ICONS = {
    # Status
    "play":       "\u23f5\ufe0e",    # ▶
    "record":     "\u23fa\ufe0e",    # ⏺ 
    "pause":      "\u23f8\ufe0e",    # ⏸
    "stop":       "\u25a0\ufe0e",    # ■
    "play-pause": "\u23ef\ufe0e",    # ⏯
    # Navigation
    "tab":        "\u21e5\ufe0e",    # ⇥ tab
    "prev":       "\u25c0\ufe0e",    # ◀
    "seek-left":  "\u23ea\ufe0e",    # ⏪
    "seek-right": "\u23e9\ufe0e",    # ⏩
    "next":       "\u23ed\ufe0e",    # ⏭
    "skip-start": "\u23ee\ufe0e",    # ⏮
    "skip-end":   "\u23ed\ufe0e",    # ⏭ (same as next)
    "eject":      "\u23cf\ufe0e",    # ⏏
    # Volume
    "vol-muted":  "\U0001f507\ufe0e", # 🔇
    "vol-low":    "\U0001f508\ufe0e", # 🔈
    "vol-med":    "\U0001f509\ufe0e", # 🔉
    "vol-high":   "\U0001f50a\ufe0e", # 🔊
    # Playlist
    "shuffle":    "\U0001f500\ufe0e", # 🔀
    "repeat":     "\U0001f501\ufe0e", # 🔁
    "repeat-one": "\U0001f502\ufe0e", # 🔂
}

# Icon widths (visual cell width - use 2 for all for consistency)
ICON_WIDTHS = {
    "play": 2, "pause": 2, "stop": 2, "play-pause": 2,
    "tab": 2, "prev": 2, "seek-left": 2, "seek-right": 2,
    "next": 2, "skip-start": 2, "skip-end": 2,
    "eject": 2,
    "vol-muted": 2, "vol-low": 2, "vol-med": 2, "vol-high": 2,
    "shuffle": 2, "repeat": 2, "repeat-one": 2,
}

DEFAULT_ICON_WIDTH = 2


def icon(name: str, width: int = None) -> str:
    """Return an icon wrapped in an overlay."""
    if name not in ICONS:
        symbol = "?"
    else:
        symbol = ICONS[name]
    effective_width = width if width is not None else ICON_WIDTHS.get(name, DEFAULT_ICON_WIDTH)
    return overlay(symbol, effective_width)


# ─────────────────────────────────────────────────────────────────────────────
# Color helpers
# ─────────────────────────────────────────────────────────────────────────────

def colorize(text: str, color: str) -> str:
    """Add ANSI color to text, then reset."""
    return f"{color}{text}\033[0m"


def overlay(content: str, width: int = 2) -> str:
    """Wrap content in a fixed-width overlay slot."""
    return f"{' ' * width}\x1b7\x1b[{width}D{content}\x1b[0m\x1b8"

# ─────────────────────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PlayerState:
    player: str = ""
    status: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    position: float = 0.0
    length: float = 0.0
    volume: int = 0
    loop: str = "None"
    shuffle: str = "false"
    dirty: bool = True

state = PlayerState()

# Format for metadata parsing (newline separator - safe from user content)
METADATA_FORMAT = "\n".join([
    # Basic info
    "{{playerName}}",
    "{{status}}",
    "{{title}}",
    "{{artist}}",
    "{{album}}",
    # Track details
    "{{albumArtist}}",
    "{{trackNumber}}",
    "{{discNumber}}",
    "{{genre}}",
    "{{xesam:explicit}}",
    "{{subtitle}}",
    "{{asText}}",
    # People
    "{{composer}}",
    "{{lyricist}}",
    "{{conductor}}",
    "{{performer}}",
    "{{arranger}}",
    # Dates & IDs
    "{{releaseDate}}",
    "{{contentCreated}}",
    "{{musicBrainzTrackId}}",
    "{{musicBrainzAlbumId}}",
    "{{musicBrainzArtistIds}}",
    # Other
    "{{comment}}",
    "{{mood}}",
    "{{url}}",
    "{{userHomePage}}",
    "{{useCount}}",
    "{{autoRating}}",
    "{{audioBPM}}",
    "{{language}}",
    "{{lyrics}}",
    # Playback
    "{{position}}",
    "{{mpris:length}}",
    "{{volume}}",
    "{{loopStatus}}",
    "{{loop}}",
    "{{shuffle}}",
    # Extra
    "{{mpris:artUrl}}",
    "{{mpris:trackid}}",
])

# Debounce follower updates after commands (in seconds)
COMMAND_DEBOUNCE = 0.3
last_command_time = 0.0

# ─────────────────────────────────────────────────────────────────────────────
# Shutdown handling
# ─────────────────────────────────────────────────────────────────────────────

shutdown_requested = False

def request_shutdown(signum, frame=None):
    global shutdown_requested
    shutdown_requested = True

def setup_signals():
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, request_shutdown)
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, request_shutdown)
    if hasattr(signal, 'SIGQUIT'):
        signal.signal(signal.SIGQUIT, request_shutdown)
    atexit.register(cleanup)

# ─────────────────────────────────────────────────────────────────────────────
# Process management
# ─────────────────────────────────────────────────────────────────────────────

processes: list[subprocess.Popen] = []

def cleanup():
    for proc in list(processes):
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=0.5)
                except OSError:
                    pass
    processes.clear()

def cleanup_proc(proc: Optional[subprocess.Popen]) -> None:
    if not proc:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=0.5)
        except (subprocess.TimeoutExpired, OSError):
            pass
    except OSError:
        pass
    if proc in processes:
        processes.remove(proc)

# ─────────────────────────────────────────────────────────────────────────────
# UI Rendering
# ─────────────────────────────────────────────────────────────────────────────

def render_ui():
    """Render the full UI to stdout."""
    # Move cursor to top of UI area
    move_cursor(1, 1)
    
    # Build rows dynamically - skip None (missing metadata)
    info_rows = [
        album_row(),
        track_row(),
        artist_row(),
    ]
    visible_info = [r for r in info_rows if r is not None]
    
    # Build all rows
    rows = [
        border_top(),
        header_row(),
        border_mid(),
    ]
    rows.extend(visible_info)
    rows.extend([
        border_mid(),
        progress_row(),
        volume_row(),
        border_mid(),
        toolbar_row(),
        border_bot(),
    ])
    
    # Calculate dynamic UI height
    ui_height = len(rows)
    
    # Print rows with clears to remove old content below
    for row_text in rows:
        sys.stdout.write(row_text)
        # Clear to end of line
        sys.stdout.write("\033[K\n")
    
    # Clear remaining lines from old content
    for _ in range(ui_height, Config.UI_HEIGHT):
        sys.stdout.write("\033[K\n")
    
    # Move cursor back to top for next refresh
    move_cursor(1, 1)
    sys.stdout.flush()
    state.dirty = False
# ─────────────────────────────────────────────────────────────────────────────

def get_available_players() -> List[str]:
    try:
        result = subprocess.run(
            ["playerctl", "--list-all"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode != 0:
            return []
        return [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []

def player_args() -> List[str]:
    return ["-p", current_player] if current_player else []

def reset_state():
    """Reset all state fields."""
    state.player = ""
    state.status = "No player"
    state.title = ""
    state.artist = ""
    state.album = ""
    state.position = 0.0
    state.length = 0.0
    state.volume = 0.0
    state.loop = "None"
    state.shuffle = "false"
    state.dirty = True

def switch_player(pos_proc, meta_proc) -> tuple:
    """Switch to next player."""
    global current_player, current_player_idx, available_players

    cleanup_proc(pos_proc)
    cleanup_proc(meta_proc)

    available_players = get_available_players()
    if not available_players:
        reset_state()
        return None, None

    current_player_idx = (current_player_idx + 1) % len(available_players)
    current_player = available_players[current_player_idx]

    new_pos_proc = start_position_follower()
    new_meta_proc = start_metadata_follower()

    if new_pos_proc is None or new_meta_proc is None:
        reset_state()
        return new_pos_proc, new_meta_proc

    result = run_playerctl("--format", METADATA_FORMAT, "metadata")
    if result:
        data = parse_metadata(result)
        update_state_from_metadata(data)
    else:
        # Player exists but has no metadata - still show the player name
        state.player = current_player
        state.status = "Stopped"
        state.dirty = True

    return new_pos_proc, new_meta_proc

def run_playerctl(*args) -> str:
    """Run playerctl command, return stdout stripped."""
    try:
        result = subprocess.run(
            ["playerctl"] + player_args() + list(args),
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""

def start_position_follower() -> Optional[subprocess.Popen]:
    """Start background position follower."""
    try:
        # Use --format '{{position}}' with --follow to get continuous updates
        proc = subprocess.Popen(
            ["playerctl"] + player_args() + ["--format", "{{position}}", "--follow", "position"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        processes.append(proc)
        return proc
    except OSError:
        return None

def start_metadata_follower() -> Optional[subprocess.Popen]:
    """Start background metadata follower."""
    try:
        proc = subprocess.Popen(
            ["playerctl"] + player_args() + ["--format", METADATA_FORMAT, "--follow", "metadata"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        processes.append(proc)
        return proc
    except OSError:
        return None

def _parse_volume(raw: str) -> int:
    """Convert volume float (0.0-1.0) to int (0-100)."""
    if not raw:
        return 0
    try:
        vol = float(raw)
        vol = max(0.0, min(1.0, vol))  # clamp
        return round(vol * 100)
    except (ValueError, TypeError):
        return 0


def parse_metadata(raw: str) -> dict:
    """Parse metadata using newline delimiter."""
    parts = raw.split("\n")
    if len(parts) < 10:
        return {}
    try:
        return {
            # Basic info
            "player": parts[0] or "",
            "status": parts[1] or "",
            "title": parts[2] or "",
            "artist": parts[3] or "",
            "album": parts[4] or "",
            # Track details
            "albumArtist": parts[5] or "",
            "trackNumber": parts[6] or "",
            "discNumber": parts[7] or "",
            "genre": parts[8] or "",
            "explicit": parts[9] or "false",
            "subtitle": parts[10] or "",
            "asText": parts[11] or "",
            # People
            "composer": parts[12] or "",
            "lyricist": parts[13] or "",
            "conductor": parts[14] or "",
            "performer": parts[15] or "",
            "arranger": parts[16] or "",
            # Dates & IDs
            "releaseDate": parts[17] or "",
            "contentCreated": parts[18] or "",
            "musicBrainzTrackId": parts[19] or "",
            "musicBrainzAlbumId": parts[20] or "",
            "musicBrainzArtistIds": parts[21] or "",
            # Other
            "comment": parts[22] or "",
            "mood": parts[23] or "",
            "url": parts[24] or "",
            "userHomePage": parts[25] or "",
            "useCount": parts[26] or "",
            "autoRating": parts[27] or "",
            "audioBPM": parts[28] or "",
            "language": parts[29] or "",
            "lyrics": parts[30] or "",
            # Playback
            "position": float(parts[31]) / 1_000_000 if parts[31] else 0.0,
            "length": float(parts[32]) / 1_000_000 if parts[32] else 0.0,
            "volume": _parse_volume(parts[33]),
            "loopStatus": parts[34] or "None",
            "loop": parts[35] or "None",
            "shuffle": parts[36] or "false",
            # Extra
            "artUrl": parts[37] or "",
            "trackid": parts[38] or "",
        }
    except (ValueError, IndexError):
        return {}

# ─────────────────────────────────────────────────────────────────────────────
# Theme Configuration
# ─────────────────────────────────────────────────────────────────────────────

class Theme:
    # Catppuccin Mocha palette (24-bit RGB: \033[38;2;R;G;Bm)
    
    # Status colors
    PLAYING = os.environ.get("TPCTL_PLAYING", "\033[38;2;166;227;161m")   # green
    PAUSED = os.environ.get("TPCTL_PAUSED", "\033[38;2;249;226;175m")   # yellow
    STOPPED = os.environ.get("TPCTL_STOPPED", "\033[38;2;108;112;134m")   # overlay0
    RECORDING = os.environ.get("TPCTL_RECORDING", "\033[38;2;243;139;168m")  # red
    
    # Key hints
    KEY_HINT = os.environ.get("TPCTL_KEY_HINT", "\033[38;2;137;180;250m")  # blue
    
    # Borders & labels
    BORDER = os.environ.get("TPCTL_BORDER", "\033[38;2;108;112;134m")   # overlay0
    DIM = os.environ.get("TPCTL_DIM", "\033[38;2;108;112;134m")  # overlay0
    
    # Progress bar
    PROGRESS_FILL = os.environ.get("TPCTL_PROGRESS_FILL", "\033[38;2;137;180;250m")  # blue
    PROGRESS_EMPTY = os.environ.get("TPCTL_PROGRESS_EMPTY", "\033[38;2;108;112;134m")  # overlay0
    
    # Volume bar (gradient: red → yellow → green)
    VOL_MUTED = os.environ.get("TPCTL_VOL_MUTED", "\033[38;2;243;139;168m")    # red
    VOL_LOW = os.environ.get("TPCTL_VOL_LOW", "\033[38;2;249;226;175m")     # yellow
    VOL_MED = os.environ.get("TPCTL_VOL_MED", "\033[38;2;166;227;161m")     # green
    VOL_HIGH = os.environ.get("TPCTL_VOL_HIGH", "\033[38;2;166;227;161m")    # bright green
    VOL_EMPTY = os.environ.get("TPCTL_VOL_EMPTY", "\033[38;2;108;112;134m")  # overlay0
    
    RESET = "\033[0m"


def status_color(status: str) -> str:
    """Get color for status."""
    colors = {
        "Playing": Theme.PLAYING,
        "Paused": Theme.PAUSED,
        "Stopped": Theme.STOPPED,
        "Recording": Theme.RECORDING,
    }
    return colors.get(status, Theme.STOPPED)



# ─────────────────────────────────────────────────────────────────────────────
# UI Row Builders
# ─────────────────────────────────────────────────────────────────────────────

def border_top() -> str:
    """Top border: ┌ followed by ─ repeated, then ┐"""
    return f"{Theme.BORDER}┌{"─" * (Config.UI_WIDTH - 2)}┐{Theme.RESET}"

def border_mid() -> str:
    """Middle border: ├ followed by ─ repeated, then ┤"""
    return f"{Theme.BORDER}├{"─" * (Config.UI_WIDTH - 2)}┤{Theme.RESET}"

def border_bot() -> str:
    """Bottom border: └ followed by ─ repeated, then ┘"""
    return f"{Theme.BORDER}└{"─" * (Config.UI_WIDTH - 2)}┘{Theme.RESET}"


# Width constants for header row
STATUS_WIDTH = 12  # 2 overlay + 1 space + 9 max "recording"
SWITCH_WIDTH = 8   # 2 overlay + 1 space + 6 "switch"
GAP = 2             # gap between slots


def time_width() -> int:
    """Width of formatted time (based on length)."""
    if state.length > 0:
        return len(format_time(state.length))
    return 5  # minimum "0:00"


def _status_icon(status: str) -> str:
    """Get icon name for status."""
    icons = {
        "Playing": "play",
        "Paused": "pause",
        "Stopped": "stop",
        "Recording": "record",
    }
    return icons.get(status, "stop")



def _format_player_name(player: str) -> str:
    """Format player name: strip .instanceN suffix."""
    if not player:
        return ""
    if ".instance" in player:
        return player.split(".instance")[0]
    return player


def header_row() -> str:
    """Header row with status, player name, and switch."""
    # Calculate widths
    inner = Config.UI_WIDTH - 4
    player_width = inner - STATUS_WIDTH - SWITCH_WIDTH - 2  # -2 for row() gaps

    # Status part: 12 visible chars
    status_icon = icon(_status_icon(state.status))
    if state.status == "Playing":
        status_text = colorize(f"{status_icon} playing  ", status_color(state.status))
    elif state.status == "Paused":
        status_text = colorize(f"{status_icon} paused   ", status_color(state.status))
    elif state.status == "Stopped":
        status_text = colorize(f"{status_icon} stopped  ", status_color(state.status))
    elif state.status == "Recording":
        status_text = colorize(f"{status_icon} recording", status_color(state.status))
    else:
        status_text = colorize(f"{status_icon} {state.status.lower()}", status_color(state.status))

    # Player part - extra space padding, truncate if needed
    player_name = _format_player_name(state.player)
    if len(player_name) > player_width:
        player_name = truncate(player_name, player_width)
    player_name = f" {player_name} "  # extra space padding

    # Switch part: icon + space + "switch" (no overlay, just inline icon)
    if len(available_players) > 1:
        switch_text = f"{colorize(ICONS['tab'], Theme.KEY_HINT)} switch"
    else:
        switch_text = ""

    return row(
        (status_text, STATUS_WIDTH, STATUS_WIDTH, '<'),
        (player_name, player_width, '^'),
        (switch_text, SWITCH_WIDTH, '>'),
    )


def _info_row(label: str, value: str):
    """Info row: label (7) + value (remaining). Returns None if value empty."""
    if not value:
        return None
    inner = Config.UI_WIDTH - 4
    lw, gap = 7, 1
    vw = inner - lw - gap
    label_colored = colorize(label.rjust(lw), Theme.DIM)
    return row((label_colored, lw, '>'), (truncate(value, vw), vw, '<'))


def album_row():
    return _info_row("Album:", state.album)


def track_row():
    return _info_row("Track:", state.title)


def artist_row():
    return _info_row("Artist:", state.artist)

def progress_row():
    """Progress row: time + bar + time."""
    inner = Config.UI_WIDTH - 4
    start = format_time(state.position)  # elapsed time: MM:SS
    end = format_time_total(state.length)  # total time: shows hours if needed
    bar_w = inner - len(start) - 1 - 1 - len(end)  # inner - start - gap - gap - end
    bar = progress_bar(state.position, state.length, bar_w)
    # Save time widths for volume row alignment
    state._start_time_w = len(start)
    state._end_time_w = len(end)
    return row(
        (start, len(start), '<'),
        (bar, bar_w, '^'),
        (end, len(end), '>')
    )

def _volume_icon(vol: int) -> str:
    """Get icon name for volume level (vol is 0-100)."""
    if vol == 0:
        return "vol-muted"
    elif vol < 33:
        return "vol-low"
    elif vol < 66:
        return "vol-med"
    else:
        return "vol-high"


def tool(icon_name: str, text: str, highlight: str) -> str:
    """Format a toolbar tool: icon + text with specified char(s) highlighted."""
    icon_part = icon(icon_name)
    highlighted = colorize(highlight, Theme.KEY_HINT)
    return f"{icon_part}{text.replace(highlight, highlighted, 1)}"


# Known widths for toolbar tools (overlay(2) + icon(1) + space(1) + text)
TOOL_SEEK = 7    # "←→ seek"
TOOL_VOL = 9      # "↑↓ volume"
TOOL_MUTE = 4     # "mute"
TOOL_PAUSE = 8    # "⏸ pause" 
TOOL_PREV = 7     # "⏮  prev"
TOOL_NEXT = 7     # "⏭  next"
TOOL_CLOSE = 11   # "esc/q close"


def toolbar_row():
    """Toolbar with controls."""
    inner = Config.UI_WIDTH - 4  # 68
    
    # Build each tool
    seek = f"{colorize('←→', Theme.KEY_HINT)} seek"
    vol = f"{colorize('↑↓', Theme.KEY_HINT)} volume"
    mute = f"{colorize('m', Theme.KEY_HINT)}ute"
    
    if state.status == "Playing":
        play_pause = tool("pause", "␣pause", '␣')
    else:
        play_pause = tool("play", "␣ play", '␣')
    
    prev = tool("skip-start", " prev", "p")
    next_ = tool("skip-end", " next", "n")
    close = f"{colorize('esc/q', Theme.KEY_HINT)} close"
    
    # Combine all tools with 2-space separator
    tools = " " + "  ".join([seek, vol, mute, play_pause, prev, next_, close])
    
    # Known widths: seek(7) + vol(9) + mute(4) + pause(7) + prev(8) + next(8) + close(11)
    # + 6 separators ("  ") + leading space = 67
    total_width = TOOL_SEEK + TOOL_VOL + TOOL_MUTE + TOOL_PAUSE + TOOL_PREV + TOOL_NEXT + TOOL_CLOSE + 6*2 + 1
    return row((tools, inner, total_width, '^'))


def volume_row():
    """Volume row: icon + bar + percentage."""
    vol_pct = state.volume  # already int 0-100
    pct_text = f"{vol_pct}%"
    start_w = getattr(state, '_start_time_w', None) or time_width()
    end_w = getattr(state, '_end_time_w', None) or time_width()
    pct_text = pct_text.rjust(end_w)
    vol_icon = icon(_volume_icon(vol_pct), start_w)
    bar_w = Config.UI_WIDTH - 4 - start_w - 1 - 1 - end_w
    bar = volume_bar(vol_pct, bar_w)
    return row(
        (vol_icon, start_w, '<'),
        (bar, bar_w, '^'),
        (pct_text, end_w, '>')
    )

def update_state_from_metadata(data: dict):
    """Update state from parsed metadata dict."""
    import time
    # Debounce: skip if update came too soon after our optimistic update
    if time.time() - last_command_time < COMMAND_DEBOUNCE:
        return
    changed = False
    for key, value in data.items():
        if getattr(state, key, None) != value:
            setattr(state, key, value)
            changed = True
    if changed:
        state.dirty = True

# ─────────────────────────────────────────────────────────────────────────────
# UI Rendering
# ─────────────────────────────────────────────────────────────────────────────

def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    if Config.BG:
        sys.stdout.write(f"\033[48;2;{Config.BG}m")
    sys.stdout.flush()

def move_cursor(row: int, col: int):
    sys.stdout.write(f"\033[{row};{col}H")

import re

ANSI_PATTERN = re.compile(r'\x1b\[[0-9;]*m')
CURSOR_MOVE_PATTERN = re.compile(r'\x1b\[[0-9;]*[DCuCBAH]')

def row(*slots) -> str:
    """Build a content row from slots.
    
    Each slot is (content, slot_width, alignment) or
    (content, slot_width, content_width, alignment) where content_width
    is the visible length when content has ANSI codes.
    """
    # Filter out None slots, normalize to (content, width, content_width, alignment)
    valid_slots = []
    for s in slots:
        if s is None:
            continue
        if len(s) == 3:
            content, width, alignment = s
            content_width = None  # use len(content)
        else:
            content, width, content_width, alignment = s
        valid_slots.append((content, width, content_width, alignment))
    
    if not valid_slots:
        return "│ │"
    
    parts = []
    for i, (content, width, content_width, alignment) in enumerate(valid_slots):
        actual_len = content_width if content_width is not None else len(content)
        if actual_len < width:
            pad_len = width - actual_len
            if alignment == '>':
                content = " " * pad_len + content
            elif alignment == '^':
                left_len = pad_len // 2
                right_len = pad_len - left_len
                content = " " * left_len + content + " " * right_len
            else:  # '<' or default
                content = content + " " * pad_len
        parts.append(content)
        if i < len(valid_slots) - 1:
            parts.append(" ")  # 1-space gap
    
    content_str = "".join(parts)
    
    return f"{Theme.BORDER}│{Theme.RESET} {content_str} {Theme.BORDER}│{Theme.RESET}"

def truncate(text: str, width: int) -> str:
    """Truncate text to visible width, add ellipsis if needed."""
    text = text.replace("\n", " ").strip()
    plain = ANSI_PATTERN.sub('', text)
    if len(plain) > width:
        # Build result keeping ANSI codes, truncating visible chars
        result = ""
        visible = 0
        i = 0
        while visible < width - 1 and i < len(text):
            if text[i] == '\x1b':
                # Copy entire ANSI sequence
                end = text.find('m', i)
                if end > i:
                    result += text[i:end+1]
                    i = end + 1
                else:
                    i += 1
            else:
                result += text[i]
                visible += 1
                i += 1
        return result + "…"
    return text

def format_time(seconds: float) -> str:
    """Format seconds as MM:SS (for elapsed time)."""
    if seconds <= 0:
        return "0:00"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def format_time_total(seconds: float) -> str:
    """Format total track length, shows hours for long tracks."""
    if seconds <= 0:
        return "0:00"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"

def progress_bar(current: float, total: float, width: int) -> str:
    if total <= 0:
        return "─" * width
    filled = min(int((current / total) * width), width)
    empty = width - filled
    return Theme.PROGRESS_FILL + "━" * filled + Theme.PROGRESS_EMPTY + "━" * empty + Theme.RESET

def volume_bar(volume: int, width: int) -> str:
    """Build volume bar (volume is 0-100)."""
    filled = min(int(volume * width // 100), width)
    empty = width - filled
    # Color based on volume level (volume is already 0-100)
    if volume == 0:
        fill_color = Theme.VOL_MUTED
    elif volume <= 33:
        fill_color = Theme.VOL_LOW
    elif volume <= 66:
        fill_color = Theme.VOL_MED
    else:
        fill_color = Theme.VOL_HIGH
    return f"{fill_color}{'█' * filled}{Theme.VOL_EMPTY}{'░' * empty}{Theme.RESET}"

def handle_key(key: str, seq: str = "") -> None:
    global last_command_time
    import time
    if key in {'q', 'Q'} or (key == '\x1b' and not seq):
        cleanup()
        sys.exit(0)

    if key == '\x1b':
        if seq == '[A':
            # Volume up: volume is int 0-100
            vol = min(100, state.volume + 5)
            # Format volume as float for playerctl
            vol_arg = f"{vol / 100:.2f}"
            run_playerctl("volume", vol_arg)
            state.volume = vol
            last_command_time = time.time()
        elif seq == '[B':
            # Volume down: volume is int 0-100
            vol = max(0, state.volume - 5)
            # Format volume as float for playerctl
            vol_arg = f"{vol / 100:.2f}"
            run_playerctl("volume", vol_arg)
            state.volume = vol
            last_command_time = time.time()
        elif seq == '[C':
            # Seek forward: optimistic update
            state.position = min(state.length, state.position + Config.SEEK_SECONDS)
            run_playerctl("position", f"+{Config.SEEK_SECONDS}")
            last_command_time = time.time()
        elif seq == '[D':
            # Seek backward: optimistic update
            state.position = max(0, state.position - Config.SEEK_SECONDS)
            run_playerctl("position", f"-{Config.SEEK_SECONDS}")
            last_command_time = time.time()
        else:
            return
        state.dirty = True
        return

    if key in {' ', 'p', 'P'}:
        # Optimistic update
        if state.status == "Playing":
            state.status = "Paused"
        else:
            state.status = "Playing"
        run_playerctl("play-pause")
        last_command_time = time.time()
    elif key in {'n', 'N'}:
        run_playerctl("next")
    elif key in {'b', 'B'}:
        run_playerctl("previous")
    elif key in {'s', 'S'}:
        run_playerctl("shuffle", "Toggle")
    elif key in {'l', 'L'}:
        if state.loop == "None":
            run_playerctl("loop", "Track")
        elif state.loop == "Track":
            run_playerctl("loop", "Playlist")
        else:
            run_playerctl("loop", "None")
    elif key in {'m', 'M'}:
        # Mute/unmute (volume is int 0-100)
        if state.volume > 0:
            run_playerctl("volume", "0.0")
            state.volume = 0
        else:
            run_playerctl("volume", "0.50")
            state.volume = 50
    else:
        return

    state.dirty = True

# ─────────────────────────────────────────────────────────────────────────────
# Main event loop
# ─────────────────────────────────────────────────────────────────────────────

def main():
    global current_player, current_player_idx, available_players

    setup_signals()

    # Hide cursor
    sys.stdout.write("\033[?25l")
    # Set background color if configured
    if Config.BG:
        sys.stdout.write(f"\033[48;2;{Config.BG}m")
    sys.stdout.flush()

    try:
        available_players = get_available_players()
        
        # Try to find a player that responds to metadata queries
        # If no player works, we'll still show the first one as "stopped"
        current_player = ""
        if available_players:
            for idx, player in enumerate(available_players):
                # Temporarily use this player to try metadata query
                _saved_player = current_player
                current_player = player
                initial = run_playerctl("--format", METADATA_FORMAT, "metadata")
                if initial:
                    current_player_idx = idx
                    update_state_from_metadata(parse_metadata(initial))
                    break
                current_player = _saved_player
            
            # If no player responded, use the first one anyway
            if not current_player and available_players:
                current_player_idx = 0
                current_player = available_players[0]
                state.player = current_player
                state.status = "Stopped"
                state.dirty = True
        else:
            state.status = "No MPRIS player"
            state.dirty = True

        pos_proc = start_position_follower() if current_player else None
        meta_proc = start_metadata_follower() if current_player else None

        clear_screen()

        stdin_fd = None
        old_settings = None
        is_tty = False
        if os.isatty(sys.stdin.fileno()):
            stdin_fd = sys.stdin.fileno()
            is_tty = True
            try:
                import termios
                old_settings = termios.tcgetattr(stdin_fd)
                new_settings = termios.tcgetattr(stdin_fd)
                new_settings[3] &= ~(termios.ICANON | termios.ECHO)
                new_settings[6][termios.VMIN] = 0
                new_settings[6][termios.VTIME] = 0
                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, new_settings)
            except ImportError:
                is_tty = False
                stdin_fd = None

        def build_select_list():
            fds = []
            if pos_proc and pos_proc.stdout:
                fds.append(pos_proc.stdout)
            if meta_proc and meta_proc.stdout:
                fds.append(meta_proc.stdout)
            if stdin_fd is not None:
                fds.append(stdin_fd)
            return fds

        while not shutdown_requested:
            fds = build_select_list()
            if not fds:
                time.sleep(0.1)
                continue
            readable, _, _ = select.select(fds, [], [], 0.5)

            if pos_proc and pos_proc.stdout in readable:
                # Read position line
                try:
                    ch = os.read(pos_proc.stdout.fileno(), 64)
                    if ch:
                        # May have multiple lines, take last non-empty
                        for line in reversed(ch.split(b'\n')):
                            if line.strip():
                                state.position = float(line.strip()) / 1_000_000
                                state.dirty = True
                                break
                except OSError:
                    pass
                if pos_proc.poll() is not None:
                    cleanup_proc(pos_proc)
                    pos_proc = start_position_follower() if current_player else None

            if meta_proc and meta_proc.stdout in readable:
                # Read metadata - METADATA_FORMAT has 39 fields joined by \n
                try:
                    data = os.read(meta_proc.stdout.fileno(), 4096)
                    if data:
                        decoded = data.decode('utf-8', errors='replace')
                        # Each metadata update is 39 lines (fields joined by \n)
                        # Parse all complete blocks (39 lines each)
                        lines = decoded.strip().split('\n')
                        for i in range(0, len(lines), 39):
                            block_lines = lines[i:i+39]
                            if len(block_lines) == 39:
                                block = '\n'.join(block_lines)
                                parsed = parse_metadata(block)
                                if parsed:
                                    update_state_from_metadata(parsed)
                except OSError:
                    pass

                # Check if process died
                if meta_proc.poll() is not None:
                    cleanup_proc(meta_proc)
                    meta_proc = start_metadata_follower() if current_player else None

            if stdin_fd is not None and stdin_fd in readable:
                try:
                    c = os.read(stdin_fd, 1)
                    if not c:
                        continue
                    ch = c.decode('utf-8', errors='replace')

                    if ch == '\t':
                        pos_proc, meta_proc = switch_player(pos_proc, meta_proc)
                    elif ch == '\x1b':
                        r, _, _ = select.select([stdin_fd], [], [], 0.02)
                        if stdin_fd in r:
                            c2 = os.read(stdin_fd, 1)
                            if c2:
                                ch2 = c2.decode('utf-8', errors='replace')
                                if ch2 == '[':
                                    r2, _, _ = select.select([stdin_fd], [], [], 0.1)
                                    if stdin_fd in r2:
                                        c3 = os.read(stdin_fd, 1)
                                        if c3:
                                            ch3 = c3.decode('utf-8', errors='replace')
                                            handle_key(ch, ch2 + ch3)
                                        else:
                                            handle_key(ch, '')
                                else:
                                    handle_key(ch, ch2)
                        else:
                            handle_key(ch, '')
                    else:
                        handle_key(ch, '')
                except OSError:
                    pass

            if state.dirty:
                render_ui()

    finally:
        if is_tty and old_settings:
            try:
                import termios
                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)
            except (ImportError, OSError):
                pass
        sys.stdout.write("\033[?25h")
        sys.stdout.write("\033[49m")  # Reset background
        sys.stdout.write("\033[0m")  # Reset all attributes
        sys.stdout.flush()
        clear_screen()
        cleanup()

if __name__ == "__main__":
    main()
