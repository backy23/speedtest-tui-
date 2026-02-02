"""
Output formatting module for JSON export and text output.
"""
import json
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import asdict


def create_result_json(
    client_info: Dict[str, Any],
    server_info: Dict[str, Any],
    latency_results: Dict[str, Any],
    download_results: Dict[str, Any],
    upload_results: Dict[str, Any],
    server_selection: list = None
) -> Dict[str, Any]:
    """
    Create a comprehensive JSON result matching Ookla's format.
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "client": client_info,
        "server": server_info,
        "ping": latency_results.get("latency_ms", 0),
        "jitter": latency_results.get("jitter_ms", 0),
        "pings": latency_results.get("pings", []),
        "latency": {
            "connectionProtocol": "wss",
            "tcp": {
                "jitter": latency_results.get("jitter_ms", 0),
                "rtt": {
                    "min": min(latency_results.get("pings", [0])),
                    "max": max(latency_results.get("pings", [0])),
                    "mean": sum(latency_results.get("pings", [0])) / max(len(latency_results.get("pings", [])), 1),
                    "median": sorted(latency_results.get("pings", [0]))[len(latency_results.get("pings", [0])) // 2] if latency_results.get("pings") else 0
                },
                "count": len(latency_results.get("pings", [])),
                "samples": latency_results.get("pings", [])
            }
        },
        "download": {
            "speed_bps": download_results.get("speed_bps", 0),
            "speed_mbps": download_results.get("speed_mbps", 0),
            "bytes": download_results.get("bytes_total", 0),
            "duration_ms": download_results.get("duration_ms", 0),
            "connections": download_results.get("connections", []),
            "samples": download_results.get("samples", [])
        },
        "upload": {
            "speed_bps": upload_results.get("speed_bps", 0),
            "speed_mbps": upload_results.get("speed_mbps", 0),
            "bytes": upload_results.get("bytes_total", 0),
            "duration_ms": upload_results.get("duration_ms", 0),
            "connections": upload_results.get("connections", []),
            "samples": upload_results.get("samples", [])
        }
    }
    
    if server_selection:
        result["serverSelection"] = {
            "closestPingDetails": server_selection
        }
    
    return result


def save_json(result: Dict[str, Any], filepath: str):
    """Save result to JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)


def format_text_result(
    ping_ms: float,
    jitter_ms: float,
    download_mbps: float,
    upload_mbps: float,
    server_name: str,
    isp: str,
    ip: str
) -> str:
    """Format a simple text result."""
    lines = [
        "=" * 50,
        "Speedtest Results",
        "=" * 50,
        f"Server: {server_name}",
        f"ISP: {isp}",
        f"IP: {ip}",
        "-" * 50,
        f"Ping: {ping_ms:.1f} ms (jitter: {jitter_ms:.2f} ms)",
        f"Download: {download_mbps:.2f} Mbps",
        f"Upload: {upload_mbps:.2f} Mbps",
        "=" * 50,
    ]
    return "\n".join(lines)


def format_csv_header() -> str:
    """Return CSV header line."""
    return "timestamp,server,isp,ip,ping_ms,jitter_ms,download_mbps,upload_mbps"


def format_csv_row(
    server_name: str,
    isp: str,
    ip: str,
    ping_ms: float,
    jitter_ms: float,
    download_mbps: float,
    upload_mbps: float
) -> str:
    """Format a CSV row."""
    timestamp = datetime.now().isoformat()
    return f"{timestamp},{server_name},{isp},{ip},{ping_ms:.1f},{jitter_ms:.2f},{download_mbps:.2f},{upload_mbps:.2f}"
