"""
Speed grading and comparison helpers.

Provides letter grades based on plan speed, and delta comparison
against the previous test result.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

_THRESHOLDS = [
    (0.95, "A+", "green"),
    (0.85, "A",  "green"),
    (0.75, "B",  "yellow"),
    (0.60, "C",  "yellow"),
    (0.40, "D",  "red"),
    (0.00, "F",  "red"),
]


def grade_speed(measured_mbps: float, plan_mbps: float) -> Tuple[str, str, float]:
    """
    Return (grade, color, percentage) for *measured_mbps* vs *plan_mbps*.

    ``percentage`` is measured / plan as a fraction (0..1+).
    """
    if plan_mbps <= 0:
        return ("?", "dim", 0.0)

    pct = measured_mbps / plan_mbps

    for threshold, letter, color in _THRESHOLDS:
        if pct >= threshold:
            return (letter, color, pct)

    return ("F", "red", pct)


# ---------------------------------------------------------------------------
# Delta comparison
# ---------------------------------------------------------------------------

def compare_with_previous(
    current: Dict[str, Any],
    history: List[Dict[str, Any]],
) -> Optional[Dict[str, float]]:
    """
    Compare *current* result with the most recent entry in *history*.

    Returns a dict with delta values, or None if there's no history.
    Keys: ping_delta, download_delta, upload_delta (all in their native units).
    """
    if not history:
        return None

    prev = history[-1]

    def _get_dl(entry: dict) -> float:
        dl = entry.get("download", {})
        return dl.get("speed_mbps", 0) if isinstance(dl, dict) else 0

    def _get_ul(entry: dict) -> float:
        ul = entry.get("upload", {})
        return ul.get("speed_mbps", 0) if isinstance(ul, dict) else 0

    def _get_ping(entry: dict) -> float:
        return entry.get("ping", 0)

    return {
        "ping_delta": _get_ping(current) - _get_ping(prev),
        "download_delta": _get_dl(current) - _get_dl(prev),
        "upload_delta": _get_ul(current) - _get_ul(prev),
        "prev_ping": _get_ping(prev),
        "prev_download": _get_dl(prev),
        "prev_upload": _get_ul(prev),
    }


def format_delta(value: float, unit: str, invert: bool = False) -> str:
    """
    Format a delta value with a +/- prefix and color hint.

    *invert*: True for metrics where lower is better (ping).
    """
    if abs(value) < 0.01:
        return f"[dim](same)[/dim]"

    sign = "+" if value > 0 else ""
    # For ping, negative is good; for speed, positive is good
    is_good = (value < 0) if invert else (value > 0)
    color = "green" if is_good else "red"

    return f"[{color}]{sign}{value:.1f} {unit}[/{color}]"


# ---------------------------------------------------------------------------
# Share result
# ---------------------------------------------------------------------------

def format_share_text(
    ping_ms: float,
    jitter_ms: float,
    download_mbps: float,
    upload_mbps: float,
    server_name: str,
    server_sponsor: str,
    packet_loss: float = 0.0,
) -> str:
    """Generate a plain-text shareable result block."""
    lines = [
        "Speedtest Results",
        f"Server: {server_name} ({server_sponsor})",
        f"Ping: {ping_ms:.1f} ms (jitter: {jitter_ms:.2f} ms)",
    ]
    if packet_loss > 0:
        lines.append(f"Packet Loss: {packet_loss:.1f}%")
    lines.append(f"Download: {download_mbps:.2f} Mbps")
    lines.append(f"Upload: {upload_mbps:.2f} Mbps")
    lines.append("https://github.com/backy23/speedtest-tui")
    return "\n".join(lines)
