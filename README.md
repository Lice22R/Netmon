# Netmon

A terminal-based network monitor for Linux. Displays all active TCP/UDP connections in real time — which process, which remote address, which port.

![Python](https://img.shields.io/badge/python-3.11+-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---
<img width="1841" height="791" alt="изображение" src="https://github.com/user-attachments/assets/368d00ab-728a-452d-8cdc-36991f53c3cb" />

---

## About

Netmon is a lightweight TUI application built with [Textual](https://github.com/Textualize/textual). It polls the system's network stack every 2 seconds and renders a sortable table of all active connections, including the process name, PID, protocol, local and remote addresses, and connection status.

Running without root shows connections but hides PID and process names for processes owned by other users — Linux restricts that information. Running with root gives a complete picture.

---

## Requirements

- Linux
- Python 3.11+
- [pipx](https://pipx.pypa.io/)
- Anthropic API key (optional, for AI analysis): [console.anthropic.com](https://console.anthropic.com) (This feature is not available in this build)

### Dependencies

Installed automatically by pipx:

- [textual](https://github.com/Textualize/textual) — TUI framework
- [psutil](https://github.com/giampaolo/psutil) — network connections and process info

---

## Installation

Install pipx if you don't have it (Arch Linux):

```bash
sudo pacman -S python-pipx
```

Install Netmon:

```bash
pipx install git+https://github.com/Lice22R/Netmon.git
```

Make sure `~/.local/bin` is in your PATH:

```bash
pipx ensurepath
```

Then **restart your terminal** — the `netmon` command will be available globally.

To install from a local directory instead:

```bash
pipx install /path/to/netmon
```

### Running

Without root (connection list visible, process info limited):

```bash
netmon
```

With root (full process names and PIDs for all connections — recommended):

```bash
sudo env PATH=$PATH netmon
```

`env PATH=$PATH` is needed so sudo can find `netmon` in the pipx path (`~/.local/bin`).

---

## Fish Shell Integration

If you use fish, add a wrapper function so you don't have to type the full sudo command every time:

```fish
# ~/.config/fish/functions/netmon.fish
function netmon --description "Network monitor (netmon -r for root)"
    if contains -- -r $argv; or contains -- --root $argv
        sudo -E env PATH=$PATH (which netmon)
    else
        command netmon $argv
    end
end
```

After adding the function:

```bash
netmon      # run without root
netmon -r   # run with root (will prompt for sudo password)
```

The `-r` flag is handled by the fish function and is not passed to the binary itself.

---

## Keybindings

| Key | Action |
|-----|--------|
| `R` | Manually refresh the connection table |
| `1` – `6` | Sort by column (press again to reverse order) |
| `0` | Reset sorting to default |
| `A` | Run AI analysis |
| `C` | Close the AI panel |
| `Q` | Quit |

The table refreshes automatically every 2 seconds regardless of manual refresh.

Columns and their sort keys:

| Key | Column |
|-----|--------|
| `1` | Process name |
| `2` | PID |
| `3` | Protocol |
| `4` | Local address |
| `5` | Remote address |
| `6` | Status |

---

## Logs

Connections are logged to:

```
~/.local/share/netmon/logs/netmon.log
```

Rotation: up to 5 files × 10 MB = 50 MB maximum on disk. File permissions are set to `0600` (owner-readable only). When running via sudo, the log file ownership is automatically returned to the real user so subsequent non-root runs can still write to it.

---

## AI Analysis

> **Warning:** this feature is a work in progress and has not been fully tested. Use at your own risk.

AI analysis sends your current connection data to Claude and streams back a security-focused summary: suspicious ports, unusual processes, external IPs, LISTEN sockets exposed to the network, and recommendations if anything looks off.

To use it, set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

To avoid setting it every session, add it to your shell config:

```fish
# ~/.config/fish/config.fish
set -x ANTHROPIC_API_KEY "sk-ant-..."
```

```bash
# ~/.bashrc
export ANTHROPIC_API_KEY="sk-ant-..."
```

When running with sudo, the key is forwarded automatically via `-E` / `env` in the fish wrapper:

```bash
netmon -r   # key is passed through automatically if set in your environment

# or manually:
sudo env PATH=$PATH ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY netmon
```

---

## License

MIT
