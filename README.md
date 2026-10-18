# Claude Bucks ¢

A tiny, animated Claude Code spending monitor for your desk. **Claude Bucks** displays your monthly work allocation on a **128 × 64 monochrome OLED** attached to a Raspberry Pi Pico. A little pixel-art **Clawd** keeps you company while you work—and falls asleep when you don't.

The Pico connects directly to your Mac over USB. **No Wi-Fi, separate API key, or web server is required by this project.** It reads the balance that Claude Code has already cached locally; Claude Code itself may use the network to refresh that cache.

## Features

- **Monthly balance:** Claude Bucks used, remaining, and percentage consumed, with two decimal places.
- **Minimalist display:** One progress bar and a custom pixel-drawn `¢` currency symbol.
- **Animated Clawd:** Blinking, hopping, dancing, occasional naps, and other randomized antics.
- **Sleep mode:** A large, centered sleeping Clawd while waiting for the Mac or after 15 seconds without a USB heartbeat. Clawd can also nap while connected without hiding the dashboard.
- **Status indicators:** Small symbols for fresh, stale, or unavailable usage data.
- **Local data collection:** Reads the usage-credit snapshot Claude Code caches in `~/.claude.json`.
- **CLI-first workflow:** Develop and deploy using **PDM + mpremote**, without a VS Code extension.
- **Optional background service:** A macOS LaunchAgent can start the monitor at login and restart it after unexpected exits.

## How it works

```text
Claude Code
    │ writes a local usage-credit snapshot
    ▼
~/.claude.json
    │
    ▼
mac/collector.py ──► mac/main.py ──► mac/sender.py
                                          │
                                 USB serial (JSON)
                                          │
                                          ▼
                                   Raspberry Pi Pico
                                          │
                              MicroPython + OLED driver
                                          │
                                          ▼
                                 128 × 64 OLED + Clawd
```

The **Mac** reads the budget and balance and sends both to the Pico. The **Pico** renders the dashboard and runs animations independently. There is no budget constant in the Pico firmware.

> **Data freshness:** The monitor reads a *local cache*. It does not request a fresh balance from Anthropic. The displayed amount changes only when Claude Code updates its cached usage data. The cache format is undocumented and may change.

## Hardware

- Raspberry Pi Pico with MicroPython installed.
- [Waveshare Pico-OLED-1.3](https://www.waveshare.com/wiki/Pico-OLED-1.3) — SH1107, monochrome, 64 × 128 pixels, used in **128 × 64 landscape** orientation.
- USB data cable connecting the Pico to a Mac.

The OLED module plugs onto the Pico's headers; no separate breadboard or network connection is required. Check the module's orientation before applying power.

## Setup

### 1. Flash MicroPython

If your Pico is not already running MicroPython:

1. Download the UF2 for your exact Raspberry Pi Pico model from [MicroPython](https://micropython.org/download/).
2. Hold **BOOTSEL** while connecting the Pico to USB.
3. Copy the UF2 to the mounted Pico boot volume.
4. Let the Pico reboot.

### 2. Install project dependencies

Install a compatible Python version and [PDM](https://pdm-project.org/), then clone this repository and run **from the repository root**:

```bash
pdm install
```

Verify the uploader is available:

```bash
pdm run mpremote --version
```

### 3. Deploy the Pico firmware

From the repository root:

```bash
pdm run pico-deploy
```

This uploads `pico/main.py`, `pico/oled.py`, and `pico/sprite.py` to the **root of the Pico filesystem** and resets it. MicroPython then runs `/main.py` automatically. The `mac/` directory and PDM environment are not uploaded.

With no Mac sender running, Clawd should appear on the OLED in its waiting/sleeping state.

### 4. Check Claude Code's local balance

Open Claude Code and view `/usage` so that it has an opportunity to update its cached data. Then run:

```bash
pdm run collect
```

The collector reads `cachedUsageUtilization` from `~/.claude.json`. It prefers the structured `spend` fields and falls back to `extra_usage`. These describe the account's usage-credit balance, not an individual session's token cost. The default budget is read from the same cache, so it is not separately hardcoded.

### 5. Start the monitor

```bash
pdm run mac
```

The Mac sends spending information and heartbeats over USB while the Pico runs the display and animations locally. Stop the foreground monitor with **Ctrl+C** to release the serial port.

To override the monthly allocation for a run:

```bash
pdm run mac --budget 1500
```

## PDM commands

| Command | Description |
| --- | --- |
| `pdm run collect` | Read and print locally cached Claude usage; no Pico required |
| `pdm run sender` | Test USB communication with dummy values (0–100%) |
| `pdm run mac` | Production monitor: collect and send data continuously |
| `pdm run pico-upload` | Upload Pico firmware files |
| `pdm run pico-start` | Reset the Pico; `/main.py` starts automatically |
| `pdm run pico-deploy` | Upload and restart in one command |
| `pdm run pico-files` | List files stored on the Pico |
| `pdm run pico-repl` | Open MicroPython REPL; press **Ctrl+]** to exit |
| `pdm run pico-clear` | Delete Pico filesystem contents (**destructive**) |
| `pdm run install-agent --interval 5` | Install/start the background service with a 5-second heartbeat |
| `pdm run uninstall-agent` | Stop and remove the LaunchAgent |

These aliases are defined under `[tool.pdm.scripts]` in `pyproject.toml`. `mpremote` releases its serial connection when a noninteractive command exits; a separate disconnect command is generally unnecessary.

> **Warning:** `pico-clear` removes files stored on the Pico, including `main.py` and the OLED driver. It does **not** erase MicroPython or delete the local repository. Redeploy afterward with `pdm run pico-deploy`. Depending on the exact clear command and `mpremote` version, attempting to remove the filesystem root may produce a final error even if the contents were removed.

## Run automatically on macOS

After confirming manual operation works, stop `pdm run mac` and install the LaunchAgent:

```bash
pdm run install-agent --interval 5
```

The service starts at login, attempts to reconnect if the Pico becomes unavailable, and releases the port when stopped normally. It does not require an open Terminal or VS Code window.

To remove it:

```bash
pdm run uninstall-agent
```

The service logs are located at:

```text
~/Library/Logs/ClaudeBucks/stdout.log
~/Library/Logs/ClaudeBucks/stderr.log
```

**Why a 5-second heartbeat?** The Pico enters disconnected sleep after **15 seconds** without a valid update. The Mac can send heartbeats frequently while reading the Claude Code cache less often.

> **Only one process can own the Pico's USB serial port at a time.** Stop the LaunchAgent or manual sender before deploying firmware or opening the Pico REPL. Do not run `pdm run mac` alongside a running LaunchAgent.

## OLED indicators and Clawd behavior

| Indicator | Meaning |
| --- | --- |
| `+` | Cached Claude Code balance was updated recently |
| `~` | Cached balance is **older than 15 minutes**; the USB connection may still be healthy |
| `!` | The Mac could not read the usage cache; the last valid values may still be displayed |

The indicator describes **data freshness**, not whether the USB connection is physically present.

- **Connected:** The dashboard shows monthly usage, a progress bar, `¢` amounts, and animated Clawd. It may nap without hiding the figures.
- **Waiting for Mac:** Large, centered sleeping Clawd, without explanatory text.
- **Disconnected or Mac asleep:** After **15 seconds without a valid update**, Clawd switches to deep sleep and continues its subtle sleep animations if the Pico has power.
- **Reconnected:** The next valid message wakes Clawd and restores the dashboard.

**USB power matters:** If the Mac cuts USB power while sleeping or shutting down, the Pico cannot animate. If power remains available, the watchdog and animations continue. The Pico cannot distinguish a sleeping Mac from a disconnected USB data connection; both simply stop sending messages.

## USB data format

The Mac sends newline-delimited JSON, for example:

```json
{"used": 27.54, "budget": 100.0, "status": "ok"}
```

`status` is `ok`, `stale`, or `error`. The Pico validates the values, computes remaining allocation and percentage, and draws the screen. No TCP/IP networking is involved.

## Project structure

```text
ClaudeBucks/
├── mac/
│   ├── agent.py       # Install/remove the macOS LaunchAgent
│   ├── collector.py   # Read ~/.claude.json usage-credit snapshot
│   ├── main.py        # Production loop, heartbeat, reconnect
│   └── sender.py      # USB serial transport + test mode
├── pico/
│   ├── main.py        # USB receiver and OLED dashboard
│   ├── oled.py        # Waveshare SH1107 display driver
│   └── sprite.py      # Clawd bitmap and animation engine
├── pyproject.toml     # PDM dependencies and commands
├── pdm.lock
└── README.md
```

## Troubleshooting

**`ImportError: no module named 'oled'`** — Check the Pico filesystem with `pdm run pico-files`. Firmware modules must be at the Pico filesystem root, not inside a nested `/pico` directory. Run `pdm run pico-deploy`.

**Serial port busy / `mpremote` cannot connect** — Another process has the port open. Stop `pdm run mac`, stop the LaunchAgent while deploying, and close any MicroPico REPL. On macOS, inspect the port with `lsof /dev/cu.usbmodem*`.

**OLED shows old or zero usage** — Run `pdm run collect`, compare it to Claude Code's `/usage`, and check the cache timestamp. Local session-cost tools such as `ccusage` do **not** necessarily match account-level Usage credits. The local cache may remain unchanged until Claude Code refreshes it.

**Clawd will not enter deep sleep** — Check whether a LaunchAgent or another sender is still transmitting. With all senders stopped and USB power maintained, the dashboard should switch to deep sleep after approximately 15 seconds.

**OLED turns black when Mac sleeps** — The Mac may be cutting USB power. Software cannot animate an unpowered Pico.

**Clawd randomly naps while connected** — That's intentional. Napping does not mean the USB connection is down; `~` means stale spending data, not disconnection.

## Privacy and limitations

- The monitor reads locally cached Claude Code usage; **it does not make direct Anthropic API requests**.
- The monitor does not need to read or store Claude login credentials. Never commit `~/.claude.json` or paste the full file into an issue: it may contain sensitive account details.
- The balance is the latest locally cached **usage-credit** amount, not a guaranteed live billing feed. Claude Code controls the cache schema and refresh schedule.
- The bundled collector and LaunchAgent workflow target macOS; the Pico firmware runs MicroPython.

---

*Built for one purpose: watching Clawd spend Claude Bucks, take naps, and occasionally remember he's supposed to be working.*
