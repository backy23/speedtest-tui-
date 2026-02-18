# Speedtest CLI Custom

A Python-based command-line interface for testing internet speed using Ookla's Speedtest.net servers. This client provides advanced metrics often hidden in the standard web interface.

## Screenshots

![Server Selection](https://github.com/user-attachments/assets/1200757f-a133-4700-a303-644f455b1bb3)
*Server selection and ping test*

![Download Test](https://github.com/user-attachments/assets/1c61e38d-522d-4731-9e92-0e30df48bb8f)
*Download speed measurement*

## Features

- **Detailed Latency**: Measures jitter, packet loss, and provides a histogram of ping times using WebSocket protocol.
- **Loaded Latency (Bufferbloat)**: Measures ping during download and upload to detect bufferbloat.
- **Parallel Testing**: Uses multiple concurrent connections with warm-up discard and IQM-based speed calculation for stable results.
- **Rich Interface**: Beautiful terminal dashboard using the `rich` library.
- **Test History**: Automatically saves results with sparkline trend charts (`--history`).
- **Compare with Previous**: Shows delta vs your last test after every run.
- **Speed Grading**: Grade your speed against your ISP plan (`--plan 100`).
- **Repeat Mode**: Run tests on a schedule (`--repeat 5 --interval 60`).
- **Alert Threshold**: Get warned when speed drops below a threshold (`--alert-below 50`).
- **Share Results**: Generate a shareable text block (`--share`).
- **JSON / CSV Export**: Full data export for automation and long-term monitoring.
- **pip Installable**: Install globally with `pip install .`

## Installation

### pip install (recommended)

```bash
pip install .
speedtest-tui
```

### Manual

```bash
pip install -r requirements.txt
python speedtest.py
```

### Android (Termux)

Works perfectly on Android using Termux!

```bash
pkg update && pkg upgrade
pkg install python
pip install -r requirements.txt
python speedtest.py
```

## Usage

```bash
python speedtest.py
```

### Options

| Flag | Description |
|------|-------------|
| `--simple`, `-s` | Text-only output (no dashboard) |
| `--json`, `-j` | Output JSON data |
| `--output FILE`, `-o` | Save JSON to file |
| `--csv FILE` | Append result as CSV row |
| `--share` | Print shareable result text |
| `--history` | Show past test results with sparkline trends |
| `--list-servers` | List available servers and exit |
| `--server ID` | Use a specific server by ID |
| `--ping-count N` | Number of ping samples (default: 10) |
| `--download-duration SECS` | Duration of download test (default: 10) |
| `--upload-duration SECS` | Duration of upload test (default: 10) |
| `--connections N` | Number of concurrent connections (default: 4) |
| `--repeat N` | Run the test N times (default: 1) |
| `--interval SECS` | Seconds between repeated tests (default: 60) |
| `--plan MBPS` | Your plan speed for grading (shows A+/A/B/C/D/F) |
| `--alert-below MBPS` | Alert if download drops below threshold |

### Examples

```bash
# Simple text output
python speedtest.py --simple

# Save to JSON and CSV
python speedtest.py -o result.json --csv speedlog.csv

# View test history with trend charts
python speedtest.py --history

# Grade against your 100 Mbps plan
python speedtest.py --plan 100

# Run 5 tests every 2 minutes, alert if below 50 Mbps
python speedtest.py --repeat 5 --interval 120 --alert-below 50

# Share your result
python speedtest.py --share

# Use a specific server with more pings
python speedtest.py --server 12345 --ping-count 20
```

## Running Tests

```bash
python -m unittest discover -s tests -v
```
