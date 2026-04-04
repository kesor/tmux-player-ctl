#!/usr/bin/env python3
"""
tmux-player-ctl - A tmux popup controller for MPRIS media players via playerctl.

Usage:
    tmux display-popup -x0 -y0 -w100% -h100% -E "python3 /path/to/tmux-player-ctl.py"
"""

from concurrent.futures import ThreadPoolExecutor

import os
import sys
import signal
import atexit
import subprocess
import select
import time
import re
from dataclasses import dataclass
from typing import Optional, List


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────


class Config:
    UI_WIDTH = 72  # Width of the UI box
    UI_HEIGHT = 12  # Number of rows in the UI
    SEEK_SECONDS = 10
    # Background: 24-bit RGB like "0;0;0" for black
    BG = os.environ.get("TPCTL_BG", "")  # e.g., "0;0;0" for black


# Player tracking
current_player: str = ""
available_players: List[str] = []
current_player_idx: int = -1

_playerctl_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pctl")

# ─────────────────────────────────────────────────────────────────────────────
# Icons
# ─────────────────────────────────────────────────────────────────────────────

# Unicode symbols (VS15 \uFE0E for text presentation)
ICONS = {
    # Status
    "play": "\u23f5\ufe0e",  # ▶
    "record": "\u23fa\ufe0e ",  # ⏺
    "pause": "\u23f8\ufe0e ",  # ⏸
    "stop": "\u25a0\ufe0e",  # ■
    "play-pause": "\u23ef\ufe0e",  # ⏯
    # Navigation
    "tab": "\u21e5\ufe0e",  # ⇥ tab
    "prev": "\u25c0\ufe0e",  # ◀
    "seek-left": "\u23ea\ufe0e",  # ⏪
    "seek-right": "\u23e9\ufe0e",  # ⏩
    "next": "\u23ed\ufe0e",  # ⏭
    "skip-start": "\u23ee\ufe0e",  # ⏮
    "skip-end": "\u23ed\ufe0e",  # ⏭ (same as next)
    "eject": "\u23cf\ufe0e",  # ⏏
    # Volume
    "vol-muted": "\U0001f507",  # 🔇
    "vol-low": "\U0001f508",  # 🔈
    "vol-med": "\U0001f509",  # 🔉
    "vol-high": "\U0001f50a",  # 🔊
    # Playlist
    "shuffle": "\U0001f500\ufe0e",  # 🔀
    "repeat": "\U0001f501\ufe0e",  # 🔁
    "repeat-one": "\U0001f502\ufe0e",  # 🔂
}


def icon(name: str) -> str:
    """Return the raw icon symbol."""
    return ICONS.get(name, "?")


# ─────────────────────────────────────────────────────────────────────────────
# Color helpers
# ─────────────────────────────────────────────────────────────────────────────


def colorize(text: str, color: str) -> str:
    """Add ANSI color to text, then reset."""
    return f"{color}{text}{Theme.RESET}"


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
    pre_mute_volume: int = 50  # Store volume before mute for restore on unmute
    _start_time_w: Optional[int] = (
        None  # Width of start time (set by progress_row for volume_row)
    )
    _end_time_w: Optional[int] = (
        None  # Width of end time (set by progress_row for volume_row)
    )


state = PlayerState()

# Format for metadata parsing (newline separator - safe from user content)
METADATA_FORMAT = "\n".join(
    [
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
    ]
)

# Debounce follower updates after commands (in seconds)
COMMAND_DEBOUNCE = 0.3
COMMAND_COOLDOWN = 0.05  # Minimum time between async calls
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
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, request_shutdown)
    if hasattr(signal, "SIGQUIT"):
        signal.signal(signal.SIGQUIT, request_shutdown)
    atexit.register(cleanup)


# ─────────────────────────────────────────────────────────────────────────────
# Process management
# ─────────────────────────────────────────────────────────────────────────────

processes: list[subprocess.Popen] = []


def cleanup():
    _playerctl_pool.shutdown(wait=False)
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
    # Build all rows
    rows = [
        border_top(),
        header_row(),
        border_mid(),
        album_row(),
        track_row(),
        artist_row(),
        border_mid(),
        progress_row(),
        volume_row(),
        border_mid(),
        toolbar_row(),
        border_bot(),
    ]

    # Write all lines with explicit cursor positioning (no newlines)
    for i, line in enumerate(rows):
        move_cursor(1 + i, 1)
        sys.stdout.write(line)

    sys.stdout.flush()
    state.dirty = False


# ─────────────────────────────────────────────────────────────────────────────


def get_available_players() -> List[str]:
    try:
        result = subprocess.run(
            ["playerctl", "--list-all"], capture_output=True, text=True, timeout=0.5
        )
        if result.returncode != 0:
            return []
        return [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
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
    state.volume = 0
    state.loop = "None"
    state.shuffle = "false"
    state.dirty = True


def switch_player(meta_proc) -> Optional[subprocess.Popen]:
    """Switch to next player. Returns new metadata follower process."""
    global current_player, current_player_idx, available_players

    cleanup_proc(meta_proc)

    available_players = get_available_players()
    if not available_players:
        reset_state()
        return None

    current_player_idx = (current_player_idx + 1) % len(available_players)
    current_player = available_players[current_player_idx]

    new_meta_proc = start_metadata_follower()

    if new_meta_proc is None:
        reset_state()
        return None

    result = run_playerctl("--format", METADATA_FORMAT, "metadata")
    if result:
        data = parse_metadata(result)
        update_state_from_metadata(data)
    else:
        # Player exists but has no metadata - still show the player name
        state.player = current_player
        state.status = "Stopped"
        state.dirty = True

    return new_meta_proc


def run_playerctl(*args) -> str:
    """Run playerctl command, return stdout stripped."""
    try:
        result = subprocess.run(
            ["playerctl"] + player_args() + list(args),
            capture_output=True,
            text=True,
            timeout=0.5,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def start_metadata_follower() -> Optional[subprocess.Popen]:
    """Start background metadata follower."""
    try:
        proc = subprocess.Popen(
            ["playerctl"]
            + player_args()
            + ["--format", METADATA_FORMAT, "--follow", "metadata"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
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
    PLAYING = os.environ.get("TPCTL_PLAYING", "\033[38;2;166;227;161m")  # green
    PAUSED = os.environ.get("TPCTL_PAUSED", "\033[38;2;249;226;175m")  # yellow
    STOPPED = os.environ.get("TPCTL_STOPPED", "\033[38;2;108;112;134m")  # overlay0
    RECORDING = os.environ.get("TPCTL_RECORDING", "\033[38;2;243;139;168m")  # red

    # Key hints
    KEY_HINT = os.environ.get("TPCTL_KEY_HINT", "\033[38;2;137;180;250m")  # blue

    # Borders & labels
    BORDER = os.environ.get("TPCTL_BORDER", "\033[38;2;108;112;134m")  # overlay0
    DIM = os.environ.get("TPCTL_DIM", "\033[38;2;108;112;134m")  # overlay0

    # Progress bar
    PROGRESS_FILL = os.environ.get(
        "TPCTL_PROGRESS_FILL", "\033[38;2;137;180;250m"
    )  # blue
    PROGRESS_EMPTY = os.environ.get(
        "TPCTL_PROGRESS_EMPTY", "\033[38;2;108;112;134m"
    )  # overlay0

    # Volume bar (gradient: red → yellow → green)
    VOL_MUTED = os.environ.get("TPCTL_VOL_MUTED", "\033[38;2;243;139;168m")  # red
    VOL_LOW = os.environ.get("TPCTL_VOL_LOW", "\033[38;2;249;226;175m")  # yellow
    VOL_MED = os.environ.get("TPCTL_VOL_MED", "\033[38;2;166;227;161m")  # green
    VOL_HIGH = os.environ.get(
        "TPCTL_VOL_HIGH", "\033[38;2;166;227;161m"
    )  # bright green
    VOL_EMPTY = os.environ.get("TPCTL_VOL_EMPTY", "\033[38;2;108;112;134m")  # overlay0

    # Reset includes background color so it's reapplied after each reset
    RESET = f"\033[0m{'' if not Config.BG else f'\033[48;2;{Config.BG}m'}"


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
    return f"{Theme.BORDER}┌{'─' * (Config.UI_WIDTH - 2)}┐{Theme.RESET}"


def border_mid() -> str:
    """Middle border: ├ followed by ─ repeated, then ┤"""
    return f"{Theme.BORDER}├{'─' * (Config.UI_WIDTH - 2)}┤{Theme.RESET}"


def border_bot() -> str:
    """Bottom border: └ followed by ─ repeated, then ┘"""
    return f"{Theme.BORDER}└{'─' * (Config.UI_WIDTH - 2)}┘{Theme.RESET}"


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
    status_w = 12  # 2 icon + 1 space + 9 max "recording"
    switch_w = 9  # 2 icon + 1 space + 6 "switch"
    inner_w = Config.UI_WIDTH - 4
    player_w = inner_w - status_w - switch_w + 2

    status_icon = icon(_status_icon(state.status))
    status_text = colorize(
        f"{status_icon:<2} {state.status.lower()}", status_color(state.status)
    )

    player_name = f" {truncate(_format_player_name(state.player), player_w - 2)} "

    if len(available_players) > 1:
        switch_text = f"{colorize(ICONS['tab'], Theme.KEY_HINT):^2} switch"
    else:
        switch_text = ""

    return row(
        (status_text, status_w, "<"),
        (player_name, player_w, "^"),
        (switch_text, switch_w, ">"),
    )


def _info_row(label: str, value: str):
    """Info row: label (7) + value (remaining)."""
    inner = Config.UI_WIDTH - 4
    lw, gap = 7, 1
    vw = inner - lw - gap
    label_colored = colorize(f"{label:>{lw}}", Theme.DIM)
    value_text = truncate(value, vw)
    return row(
        (label_colored, lw, ">"),
        (value_text, vw, "<"),
    )


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
    end = format_time(state.length)  # total time: shows hours if needed
    # Save time widths for volume row alignment
    state._start_time_w = len(start)
    state._end_time_w = len(end)
    bar_w = (
        inner - state._start_time_w - 1 - 1 - state._end_time_w
    )  # inner - start - gap - gap - end
    bar = progress_bar(state.position, state.length, bar_w)
    return row(
        (start, state._start_time_w, "<"),
        (bar, bar_w, "^"),
        (end, state._end_time_w, ">"),
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


def toolbar_row():
    """Toolbar with controls."""
    inner = Config.UI_WIDTH - 4

    # Build each tool
    seek = f"{colorize('←→', Theme.KEY_HINT)} seek"  # 7
    vol = f"{colorize('↑↓', Theme.KEY_HINT)} volume"  # 9
    mute = f"{colorize('m', Theme.KEY_HINT)}ute"  # 4

    if state.status == "Playing":
        play_pause = f"{colorize('␣', Theme.KEY_HINT)} pause"  # 7
    else:
        play_pause = f"{colorize('␣', Theme.KEY_HINT)} play "

    prev = f"{colorize('p', Theme.KEY_HINT)}rev"  # 4
    next_ = f"{colorize('n', Theme.KEY_HINT)}ext"  # 4
    close = f"{colorize('esc/q', Theme.KEY_HINT)} close"  # 11

    # Combine all tools with 2-space separator
    tools = "  ".join([seek, vol, mute, play_pause, prev, next_, close])

    gaps_w = 6 * 2
    tool_w = 7 + 9 + 4 + 7 + 4 + 4 + 11 + gaps_w
    pad_w = int((inner - tool_w) / 2)
    pad = " " * pad_w

    return row((f"{pad}{tools:^{tool_w}}{pad}", inner, "^"))


def volume_row():
    """Volume row: icon + bar + percentage."""
    inner_w = Config.UI_WIDTH - 4
    vol_pct = state.volume  # already int 0-100
    pct_text = f"{vol_pct}%"
    start_w = state._start_time_w or 0
    end_w = state._end_time_w or 0
    vol_icon = f" {icon(_volume_icon(vol_pct)):^2}"
    bar_w = inner_w - start_w - 1 - 1 - end_w
    bar = volume_bar(vol_pct, max(0, bar_w))
    return row(
        (f"{vol_icon:^3}", max(start_w - 1, 0), "<"),
        (bar, max(0, bar_w), "^"),
        (pct_text, end_w, ">"),
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


ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")
CURSOR_MOVE_PATTERN = re.compile(r"\x1b\[[0-9;]*[DCuCBAH]")


def row(*slots) -> str:
    """Build a content row from slots.

    Each slot is (content, slot_width, alignment), but content must already
    be padded to slot_width using f-string formatting.
    """
    valid_slots = [s for s in slots if s is not None]

    if not valid_slots:
        return "│ │"

    content_str = " ".join(
        f"{content:{align}{width}}" for content, width, align in valid_slots
    )

    return f"{Theme.BORDER}│{Theme.RESET} {content_str} {Theme.BORDER}│{Theme.RESET}"


def truncate(text: str, width: int) -> str:
    """Truncate text to visible width, add ellipsis if needed."""
    text = text.replace("\n", " ").strip()
    plain = ANSI_PATTERN.sub("", text)
    if len(plain) > width:
        # Build result keeping ANSI codes, truncating visible chars
        result = ""
        visible = 0
        i = 0
        while visible < width - 1 and i < len(text):
            if text[i] == "\x1b":
                # Copy entire ANSI sequence
                end = text.find("m", i)
                if end > i:
                    result += text[i : end + 1]
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
    if seconds <= 0:
        return "0:00"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    if minutes > 0:
        return f"{minutes}:{secs:02d}"
    return f"0:{secs:02d}"


def progress_bar(current: float, total: float, total_width: int) -> str:
    if total <= 0:
        return "─" * total_width
    filled_w = min(int((current / total) * total_width), total_width)
    empty_w = total_width - filled_w - 1
    return (
        Theme.PROGRESS_FILL
        + "━" * filled_w
        + "\u25cf"
        + Theme.PROGRESS_EMPTY
        + "━" * empty_w
        + Theme.RESET
    )


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


def run_playerctl_async(*args) -> None:
    """Fire-and-forget playerctl command. Does not block the main loop."""

    def _exec():
        try:
            subprocess.run(
                ["playerctl"] + player_args() + list(args),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=0.3,  # Fail fast if playerctl hangs
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass  # Metadata follower will reconcile state on next update

    _playerctl_pool.submit(_exec)


def handle_key(key: str, seq: str = "") -> None:
    global last_command_time
    import time

    now = time.time()
    if key != "q" and key != "Q" and key != "\x1b" and now - last_command_time < COMMAND_COOLDOWN:
        return  # Ignore rapid repeats
    last_command_time = now

    if key in {"q", "Q"} or (key == "\x1b" and not seq):
        cleanup()
        sys.exit(0)

    if key == "\x1b":
        if seq == "[A":
            # Volume up: volume is int 0-100
            vol = min(100, state.volume + 5)
            # Format volume as float for playerctl
            vol_arg = f"{vol / 100:.2f}"
            run_playerctl_async("volume", vol_arg)
            state.volume = vol
        elif seq == "[B":
            # Volume down: volume is int 0-100
            vol = max(0, state.volume - 5)
            # Format volume as float for playerctl
            vol_arg = f"{vol / 100:.2f}"
            run_playerctl_async("volume", vol_arg)
            state.volume = vol
        elif seq == "[C":
            # Seek forward: optimistic update
            state.position = min(state.length, state.position + Config.SEEK_SECONDS)
            run_playerctl_async("position", f"+{Config.SEEK_SECONDS}")
        elif seq == "[D":
            # Seek backward: optimistic update
            state.position = max(0, state.position - Config.SEEK_SECONDS)
            run_playerctl_async("position", f"-{Config.SEEK_SECONDS}")
        else:
            return
        state.dirty = True
        return

    if key == " ":
        # Optimistic update
        if state.status == "Playing":
            state.status = "Paused"
        else:
            state.status = "Playing"
        run_playerctl_async("play-pause")
    elif key in {"n", "N"}:
        run_playerctl_async("next")
    elif key in {"p", "P"}:
        run_playerctl_async("previous")
    elif key in {"s", "S"}:
        run_playerctl_async("shuffle", "Toggle")
    elif key in {"l", "L"}:
        if state.loop == "None":
            run_playerctl_async("loop", "Track")
        elif state.loop == "Track":
            run_playerctl_async("loop", "Playlist")
        else:
            run_playerctl_async("loop", "None")
    elif key in {"m", "M"}:
        # Mute/unmute (volume is int 0-100)
        if state.volume > 0:
            # Mute: store current volume for restore
            state.pre_mute_volume = state.volume
            run_playerctl_async("volume", "0.0")
            state.volume = 0
        else:
            # Unmute: restore to pre-mute volume (or 50% if first mute)
            restore_vol = state.pre_mute_volume if state.pre_mute_volume > 0 else 50
            run_playerctl_async("volume", f"{restore_vol / 100:.2f}")
            state.volume = restore_vol
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

            if meta_proc and meta_proc.stdout in readable:
                # Read metadata - METADATA_FORMAT has 39 fields joined by \n
                try:
                    data = os.read(meta_proc.stdout.fileno(), 4096)
                    if data:
                        decoded = data.decode("utf-8", errors="replace")
                        # Each metadata update is 39 lines (fields joined by \n)
                        # Parse all complete blocks (39 lines each)
                        lines = decoded.strip().split("\n")
                        for i in range(0, len(lines), 39):
                            block_lines = lines[i : i + 39]
                            if len(block_lines) == 39:
                                block = "\n".join(block_lines)
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
                    ch = c.decode("utf-8", errors="replace")

                    if ch == "\t":
                        meta_proc = switch_player(meta_proc)
                    elif ch == "\x1b":
                        r, _, _ = select.select([stdin_fd], [], [], 0.02)
                        if stdin_fd in r:
                            c2 = os.read(stdin_fd, 1)
                            if c2:
                                ch2 = c2.decode("utf-8", errors="replace")
                                if ch2 == "[":
                                    r2, _, _ = select.select([stdin_fd], [], [], 0.1)
                                    if stdin_fd in r2:
                                        c3 = os.read(stdin_fd, 1)
                                        if c3:
                                            ch3 = c3.decode("utf-8", errors="replace")
                                            handle_key(ch, ch2 + ch3)
                                        else:
                                            handle_key(ch, "")
                                else:
                                    handle_key(ch, ch2)
                        else:
                            handle_key(ch, "")
                    else:
                        handle_key(ch, "")
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
