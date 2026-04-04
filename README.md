# tmux-player-ctl

A minimal tmux popup controller for MPRIS media players via `playerctl`.

![screenshot](./screenshot.png)

## Requirements

- **tmux** 3.2+ (for popup support)
- **playerctl** (MPRIS2 command-line control)
- **python3**

## Quick Start

1. Ensure `playerctl` works with your media player:
   ```bash
   playerctl status
   ```

2. Run the controller in a tmux popup:
   ```bash
   tmux display-popup -B -xC -yC -w72 -h12 -E "./tmux-player-ctl.py"
   ```

## Keybindings

| Key | Action |
|-----|--------|
| `Space` / `p` | Toggle play/pause |
| `n` | Next track |
| `b` | Previous track |
| `←` / `→` | Seek back/forward 10s |
| `↑` / `↓` | Volume up/down 5% |
| `s` | Toggle shuffle |
| `l` | Cycle loop (none → track → playlist) |
| `m` | Mute/unmute |
| `Tab` | Switch between players |
| `q` / `Esc` | Exit |

## tmux Configuration

Add to your `~/.tmux.conf`:

```bash
# Popup controller (binds to Alt-p)
bind-key -n M-p display-popup -B -xC -yC -w72 -h12 -E "tmux-player-ctl"
```

Reload tmux config:
```bash
tmux source ~/.tmux.conf
```

Or use a fullscreen popup:

```bash
bind-key -n M-p display-popup -x0 -y0 -w100% -h100% -k -E "tmux-player-ctl"
```

## Theming

Override colors via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TPCTL_PLAYING` | green | Playing status color |
| `TPCTL_PAUSED` | yellow | Paused status color |
| `TPCTL_STOPPED` | gray | Stopped status color |
| `TPCTL_KEY_HINT` | blue | Key hints in toolbar |
| `TPCTL_BORDER` | gray | Border color |
| `TPCTL_DIM` | gray | Dim text color |
| `TPCTL_PROGRESS_FILL` | blue | Progress bar filled |
| `TPCTL_PROGRESS_EMPTY` | gray | Progress bar empty |
| `TPCTL_VOL_MUTED` | red | Volume muted |
| `TPCTL_VOL_LOW` | yellow | Volume low |
| `TPCTL_VOL_MED` | green | Volume medium |
| `TPCTL_VOL_HIGH` | green | Volume high |
| `TPCTL_BG` | (none) | Background color (e.g., "0;0;0") |

### Catppuccin Mocha Example

```bash
export TPCTL_PLAYING="\033[38;2;166;227;161m"    # green
export TPCTL_PAUSED="\033[38;2;249;226;175m"    # yellow
export TPCTL_STOPPED="\033[38;2;108;112;134m"   # gray
export TPCTL_KEY_HINT="\033[38;2;137;180;250m"  # blue
export TPCTL_BORDER="\033[38;2;108;112;134m"    # gray
export TPCTL_PROGRESS_FILL="\033[38;2;137;180;250m"
export TPCTL_PROGRESS_EMPTY="\033[38;2;108;112;134m"
```

## Installation

```bash
# Clone the repo
git clone https://github.com/yourusername/tmux-player-ctl.git
cd tmux-player-ctl

# Make executable
chmod +x tmux-player-ctl.py

# Copy to PATH (optional)
cp tmux-player-ctl.py ~/bin/tmux-player-ctl
```

## Troubleshooting

**Popup doesn't appear?**
- Ensure tmux is 3.2+ (`tmux -V`)
- Try without `-B` flag on older tmux versions

**Position doesn't update?**
- Some players (like Firefox) may not support position updates
- Volume changes may not work on all players

**Multiple players?**
- Press `Tab` to cycle through available MPRIS players
- The player name is shown in the header

## License

MIT
