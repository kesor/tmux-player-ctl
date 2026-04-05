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

Colors are specified as RGB triplets (r;g;b format). Override via environment variables:

```bash
# Example: Override playing color and background
TPCTL_PLAYING="255;100;100" TPCTL_BG="20;20;30" tmux-player-ctl.py
```

| Variable | Default | Description |
|----------|---------|-------------|
| `TPCTL_PLAYING` | 166;227;161 (green) | Playing status |
| `TPCTL_PAUSED` | 249;226;175 (yellow) | Paused status |
| `TPCTL_STOPPED` | 108;112;134 (gray) | Stopped / no player |
| `TPCTL_RECORDING` | 243;139;168 (red) | Recording status |
| `TPCTL_KEY_HINT` | 137;180;250 (blue) | Key hints in toolbar |
| `TPCTL_BORDER` | 108;112;134 (gray) | Box borders |
| `TPCTL_DIM` | 108;112;134 (gray) | Label text |
| `TPCTL_PROGRESS_FILL` | 137;180;250 (blue) | Progress bar filled |
| `TPCTL_PROGRESS_EMPTY` | 108;112;134 (gray) | Progress bar empty |
| `TPCTL_VOL_MUTED` | 243;139;168 (red) | Volume muted |
| `TPCTL_VOL_LOW` | 166;227;161 (green) | Volume low (0-50%) |
| `TPCTL_VOL_MED` | 249;226;175 (yellow) | Volume medium (50-80%) |
| `TPCTL_VOL_HIGH` | 243;139;168 (red) | Volume high (80-100%) |
| `TPCTL_VOL_EMPTY` | 17;17;27 (dark) | Volume bar empty |
| `TPCTL_BG` | (none) | Background RGB (e.g., "0;0;0") |

## Architecture

- **`Config`** - UI constants (width, seek seconds, volume step, ANSI colors)
- **`PlayerState`** - single track's metadata (status, title, artist, album, position, length, volume, loop, shuffle)
- **`PlayerTracker`** - all live state: current player, player list, index, state, last command time
- **`metadata.follower`** - background `playerctl metadata` subprocess
- **`run_playerctl`** - synchronous `playerctl` calls
- **`run_playerctl_async`** - fire-and-forget `playerctl` calls (no blocking)
- **`handle_key`** - maps keypresses to `playerctl` commands with optimistic UI updates
