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
    BAR_WIDTH = 40         # Width of progress/volume bars
    SEEK_SECONDS = 10
    VOLUME_STEP = 0.1

    # Theme colors (override via env vars)
    ACCENT     = os.environ.get("TPCTL_ACCENT",     "\033[92m")
    ACCENT_ALT = os.environ.get("TPCTL_ACCENT_ALT", "\033[93m")
    DIM        = os.environ.get("TPCTL_DIM",        "\033[90m")
    BAR_EMPTY  = os.environ.get("TPCTL_BAR_EMPTY",  "\033[90m")
    BAR_FILL   = os.environ.get("TPCTL_BAR_FILL",   "\033[97m")
    BORDER     = os.environ.get("TPCTL_BORDER",     "\033[37m")
    RESET      = "\033[0m"
    # Background: 24-bit RGB like "0;0;0" for black
    BG = os.environ.get("TPCTL_BG", "")  # e.g., "0;0;0" for black

# Player tracking
current_player: str = ""
available_players: List[str] = []
current_player_idx: int = -1

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
    volume: float = 0.0
    loop: str = "None"
    shuffle: str = "false"
    dirty: bool = True

state = PlayerState()

# Delimiter for metadata parsing (||| almost never appears in user content)
METADATA_FORMAT = "|||".join([
    "{{playerName}}", "{{status}}", "{{title}}", "{{artist}}",
    "{{album}}", "{{position}}", "{{mpris:length}}", "{{volume}}",
    "{{loop}}", "{{shuffle}}",
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
# playerctl helpers
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

def short_player_name(name: str) -> str:
    """Shorten player name by removing instance ID suffix."""
    if not name:
        return ""
    # Remove common suffixes like .instance12345
    if ".instance" in name:
        return name.split(".instance")[0]
    return name

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
        reset_state()

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
        proc = subprocess.Popen(
            ["playerctl"] + player_args() + ["--follow", "position"],
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

def parse_metadata(raw: str) -> dict:
    """Parse metadata using ||| delimiter."""
    parts = raw.split("|||")
    if len(parts) < 10:
        return {}
    try:
        return {
            "player": parts[0] or "",
            "status": parts[1] or "",
            "title": parts[2] or "",
            "artist": parts[3] or "",
            "album": parts[4] or "",
            "position": float(parts[5]) / 1_000_000 if parts[5] else 0.0,
            "length": float(parts[6]) / 1_000_000 if parts[6] else 0.0,
            "volume": float(parts[7]) if parts[7] else 0.0,
            "loop": parts[8] or "None",
            "shuffle": parts[9] or "false",
        }
    except (ValueError, IndexError):
        return {}

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

def visible_len(text: str) -> int:
    """Return visible length of text, stripping ANSI escape codes."""
    return len(ANSI_PATTERN.sub('', text))

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
    """Format seconds as MM:SS."""
    if seconds <= 0:
        return "0:00"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"

def progress_bar(current: float, total: float, width: int) -> str:
    if total <= 0:
        return "─" * width
    filled = min(int((current / total) * width), width)
    empty = width - filled
    return Config.BAR_FILL + "━" * filled + Config.BAR_EMPTY + "━" * empty + Config.RESET

def volume_bar(volume: float, width: int) -> str:
    filled = min(int(volume * width), width)
    empty = width - filled
    return Config.BAR_FILL + "█" * filled + Config.BAR_EMPTY + "░" * empty + Config.RESET

def status_icon(status: str) -> str:
    if status == "Playing":
        return "▶"  # Play symbol
    if status == "Paused":
        return "⏸"  # Pause symbol
    return "■"

def volume_icon(volume: float) -> str:
    """Return volume icon based on percentage."""
    pct = int(volume * 100)
    if pct == 0:
        return "🔇"  # Muted
    if pct <= 33:
        return "🔈"  # Low
    if pct <= 66:
        return "🔉"  # Medium
    return "🔊"  # Loud

def status_color(status: str) -> str:
    if status == "Playing":
        return Config.ACCENT
    if status == "Paused":
        return Config.ACCENT_ALT
    return Config.DIM

def render_ui():
    try:
        term_size = os.get_terminal_size()
    except OSError:
        term_size = os.terminal_size((80, 24))

    # Box layout: 11 rows
    # ┌────────────────────────────────────────────────────────────────────┐
    # │ ▶ playing                                                  [q] close│
    # ├────────────────────────────────────────────────────────────────────┤
    # │ Album:  Möbius Front '83...                                       │
    # │ Track:  Precision Strike                                           │
    # │ Artist: Matthew S Burns                                            │
    # ├────────────────────────────────────────────────────────────────────┤
    # │ 2:05 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 7:17│
    # │ 🔈   ████████████████████████████████████████████████████░░░░░░  89%│
    # ├────────────────────────────────────────────────────────────────────┤
    # │      ←→ seek  ↑↓ vol  [b]prev  [n]next  [␣]pause   [⇥] spotifyd   │
    # └────────────────────────────────────────────────────────────────────┘
    num_rows = 12
    start_row = max(1, (term_size.lines - num_rows) // 2)
    start_col = max(1, (term_size.columns - Config.UI_WIDTH) // 2)

    inner = Config.UI_WIDTH - 4
    dash_count = Config.UI_WIDTH - 2

    # Borders
    border_top = f"{Config.BORDER}┌{'─' * dash_count}┐{Config.RESET}"
    border_bot = f"{Config.BORDER}└{'─' * dash_count}┘{Config.RESET}"
    border_mid = f"{Config.BORDER}├{'─' * dash_count}┤{Config.RESET}"

    # Header
    icon = status_icon(state.status)
    color = status_color(state.status)
    status_left = f"{icon} {state.status.lower()}"
    status_right = "[q] close"
    gap = inner - visible_len(status_left) - visible_len(status_right)
    header = f"│ {color}{status_left}{' ' * gap}{Config.DIM}{status_right}{Config.RESET} │"

    # Track info - Album, Track, Artist order (album first for alignment)
    LABEL_WIDTH = 8  # "Album:  ", "Track:  ", "Artist: "
    value_width = inner - LABEL_WIDTH

    album = truncate(state.album, value_width) or "Unknown Album"
    title = truncate(state.title, value_width) or "Unknown Title"
    artist = truncate(state.artist, value_width) or "Unknown Artist"

    album_row = f"│ {Config.DIM}Album:{Config.RESET}  {album:<{value_width}} │"
    title_row = f"│ {Config.DIM}Track:{Config.RESET}  {title:<{value_width}} │"
    artist_row = f"│ {Config.DIM}Artist:{Config.RESET} {artist:<{value_width}} │"

    # Bar width for both progress and volume
    BAR_WIDTH = inner - 10  # 5 chars left time + 1 space + bar + 1 space + 5 chars right time - 3 = inner - 2
    BAR_WIDTH = max(BAR_WIDTH, 10)

    # Progress bar: "3:12  ██████████████░░░░  5:27" (no leading space, row adds it)
    pos_str = format_time(state.position)
    len_str = format_time(state.length)
    prog = progress_bar(state.position, state.length, BAR_WIDTH)
    prog_text = f"{pos_str} {prog} {len_str}"

    # Volume bar: align bar start with progress bar's time start
    # Progress: " 0:07 █████ 6:27 " (6 visible before bar)
    # Volume: " 🔊    █████  89% " (emoji ~2 + 4 spaces ≈ 6 visible before bar)
    vol_pct = round(state.volume * 100)  # round, not int, to avoid truncation errors
    if vol_pct == 100:
        vol_pct_str = "100"
    elif vol_pct >= 10:
        vol_pct_str = f"{vol_pct}%"
    else:
        vol_pct_str = f" {vol_pct}%"  # pad single digit
    vol_icon = volume_icon(state.volume)
    vol = volume_bar(state.volume, BAR_WIDTH)
    vol_text = f"{vol_icon}   {vol}  {vol_pct_str}"  # no leading space, row adds it

    prog_row = f"│ {Config.DIM}{prog_text:<{inner}}{Config.RESET} │"
    vol_row = f"│ {Config.DIM}{vol_text:<{inner}}{Config.RESET} │"

    # Controls row - CENTERED
    short_name = short_player_name(current_player) if current_player else "no player"
    pause_text = "pause" if state.status == "Playing" else " play"  # " play" = 5 chars same as "pause"
    player_text = f"[⇥] {short_name}" if available_players else "no player"
    ctrl_parts = [
        "←→ seek",
        "↑↓[m]vol",
        "[b]prev",
        "[n]next",
        f"[␣]{pause_text}",
        player_text,
    ]
    ctrl_text = "  ".join(ctrl_parts)

    # Center the controls text
    ctrl_len = visible_len(ctrl_text)
    if ctrl_len < inner:
        padding = (inner - ctrl_len) // 2
        ctrl_text = " " * padding + ctrl_text

    ctrl_row = f"│ {Config.DIM}{ctrl_text:<{inner}}{Config.RESET} │"

    lines = [
        border_top,
        header,
        border_mid,
        album_row,
        title_row,
        artist_row,
        border_mid,
        prog_row,
        vol_row,
        border_mid,
        ctrl_row,
        border_bot,
    ]

    # Write all lines
    sys.stdout.write("\033[J")
    for i, line in enumerate(lines):
        move_cursor(start_row + i, start_col)
        sys.stdout.write(line)
    sys.stdout.flush()

    state.dirty = False

# ─────────────────────────────────────────────────────────────────────────────
# Keyboard handling
# ─────────────────────────────────────────────────────────────────────────────

def handle_key(key: str, seq: str = "") -> None:
    global last_command_time
    import time
    if key in {'q', 'Q'} or (key == '\x1b' and not seq):
        cleanup()
        sys.exit(0)

    if key == '\x1b':
        if seq == '[A':
            # Volume up: optimistic update, work with integer 0-100
            vol_pct = round(state.volume * 100)  # round, not int, to avoid truncation errors
            vol_pct = min(100, vol_pct + 5)
            # Format volume correctly (0.0 to 1.0)
            if vol_pct >= 100:
                vol_arg = "1.0"
            elif vol_pct < 10:
                vol_arg = f"0.0{vol_pct}"
            else:
                vol_arg = f"0.{vol_pct}"
            run_playerctl("volume", vol_arg)
            # Immediately show our cached value
            state.volume = vol_pct / 100.0
            last_command_time = time.time()
        elif seq == '[B':
            # Volume down: optimistic update, work with integer 0-100
            vol_pct = round(state.volume * 100)  # round, not int, to avoid truncation errors
            vol_pct = max(0, vol_pct - 5)
            if vol_pct >= 100:
                vol_arg = "1.0"
            elif vol_pct < 10:
                vol_arg = f"0.0{vol_pct}"
            else:
                vol_arg = f"0.{vol_pct}"
            run_playerctl("volume", vol_arg)
            # Immediately show our cached value
            state.volume = vol_pct / 100.0
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
        # Mute/unmute
        if state.volume > 0:
            run_playerctl("volume", "0")
            state.volume = 0.0
        else:
            run_playerctl("volume", "0.5")
            state.volume = 0.5
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
        if available_players:
            current_player_idx = 0
            current_player = available_players[0]

        if current_player:
            initial = run_playerctl("--format", METADATA_FORMAT, "metadata")
            if initial:
                update_state_from_metadata(parse_metadata(initial))
        else:
            state.status = "No player"
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
                        # May have multiple lines, take last
                        lines = ch.split(b'\n')
                        if lines[-1]:
                            last = lines[-1].strip()
                            if last:
                                state.position = float(last) / 1_000_000
                                state.dirty = True
                except OSError:
                    pass
                if pos_proc.poll() is not None:
                    cleanup_proc(pos_proc)
                    pos_proc = start_position_follower() if current_player else None

            if meta_proc and meta_proc.stdout in readable:
                # Read metadata
                try:
                    data = os.read(meta_proc.stdout.fileno(), 4096)
                    if data:
                        lines = data.split(b'\n')
                        for line in lines:
                            if line:
                                parsed = parse_metadata(line.decode('utf-8', errors='replace').strip())
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
