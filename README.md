# `tmux-player-ctl`

A minimal tmux popup controller for [MPRIS](https://specifications.freedesktop.org/mpris-spec/) media players via [`playerctl`](https://github.com/altdesktop/playerctl).

![screenshot](./screenshot.png)

## Features

- **Real-time metadata** - background follower process watches for player changes instantly
- **Full playback controls** - play/pause, previous, next, seek ±10s, volume ±5%, mute
- **Loop & shuffle** - cycle loop mode (none → track → playlist), toggle shuffle
- **Progress bar** - live position indicator with elapsed/total time
- **Volume bar** - color-coded volume level (muted/low/med/high)
- **Multi-player** - switch between MPRIS players with `Tab`
- **Optimistic UI** - instant feedback on keypresses, rolls back if player rejects
- **24-bit ANSI colors** - theming via environment variables
- **Signal-safe** - clean exit on `SIGINT`/`SIGTERM`

## Requirements

- **tmux** 3.2+
- **playerctl**
- **python** 3.0+

## Quick Start

```bash
# Ensure playerctl works
playerctl status

# Run in a tmux popup
tmux display-popup -B -w72 -h12 -E "tmux-player-ctl.py"
```

## Keybindings

| Key | Action |
|-----|--------|
| `Space` | Toggle play/pause |
| `p` | Previous track |
| `n` | Next track |
| `←` / `→` | Seek back/forward 10s |
| `↑` / `↓` | Volume up/down 5% |
| `s` | Toggle shuffle |
| `l` | Cycle loop (none → track → playlist) |
| `m` | Mute/unmute (remembers previous volume) |
| `Tab` | Switch between players |
| `q` / `Esc` | Exit |

## Configure `tmux`

```bash
# Compact popup (72×12, centered)
bind-key -n M-p display-popup -B -w72 -h12 -E "tmux-player-ctl"
```

## Theming

All colors use ANSI 24-bit RGB sequences. Override via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TPCTL_PLAYING` | green | Playing status |
| `TPCTL_PAUSED` | yellow | Paused status |
| `TPCTL_STOPPED` | gray | Stopped / no player |
| `TPCTL_KEY_HINT` | blue | Key hints in toolbar |
| `TPCTL_BORDER` | gray | Box borders |
| `TPCTL_DIM` | gray | Label text |
| `TPCTL_ACCENT` | green | Accent color |
| `TPCTL_ACCENT_ALT` | yellow | Alternate accent |
| `TPCTL_PROGRESS_FILL` | blue | Progress bar filled |
| `TPCTL_PROGRESS_EMPTY` | gray | Progress bar empty |
| `TPCTL_VOL_MUTED` | red | Volume muted |
| `TPCTL_VOL_LOW` | yellow | Volume low |
| `TPCTL_VOL_MED` | green | Volume medium |
| `TPCTL_VOL_HIGH` | green | Volume high |
| `TPCTL_VOL_EMPTY` | gray | Volume bar empty |
| `TPCTL_BG` | (none) | Background RGB |

## Architecture

- **`Config`** - UI constants (width, seek seconds, volume step, ANSI colors)
- **`PlayerState`** - single track's metadata (status, title, artist, album, position, length, volume, loop, shuffle)
- **`PlayerTracker`** - all live state: current player, player list, index, state, last command time
- **`metadata.follower`** - background `playerctl metadata` subprocess
- **`run_playerctl`** - synchronous `playerctl` calls
- **`run_playerctl_async`** - fire-and-forget `playerctl` calls (no blocking)
- **`handle_key`** - maps keypresses to `playerctl` commands with optimistic UI updates
