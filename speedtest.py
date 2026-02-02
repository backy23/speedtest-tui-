#!/usr/bin/env python3
import argparse
import asyncio
import sys
import json
from typing import Optional

from client.api import SpeedtestAPI, Server
from client.latency import LatencyTester, ServerLatencyResult
from client.download import SimpleDownloadTester
from client.upload import UploadTester
from ui.dashboard import (
    console, print_header, print_client_info, print_server_selection,
    print_latency_details, print_speed_result, print_final_results,
    ProgressDisplay
)
from ui.output import create_result_json, save_json


# Constants for parameter validation
MIN_PING_COUNT = 1
MAX_PING_COUNT = 100
MIN_DURATION = 1.0
MAX_DURATION = 300.0
DEFAULT_DURATION = 10.0
MIN_CONNECTIONS = 1
MAX_CONNECTIONS = 32
DEFAULT_CONNECTIONS = 4


def validate_parameters(
    ping_count: int,
    download_duration: float,
    upload_duration: float,
    connections: int
) -> None:
    """Validate speedtest parameters and raise ValueError if invalid."""
    if not MIN_PING_COUNT <= ping_count <= MAX_PING_COUNT:
        raise ValueError(f"Ping count must be between {MIN_PING_COUNT} and {MAX_PING_COUNT}")
    
    if not MIN_DURATION <= download_duration <= MAX_DURATION:
        raise ValueError(f"Download duration must be between {MIN_DURATION} and {MAX_DURATION} seconds")
    
    if not MIN_DURATION <= upload_duration <= MAX_DURATION:
        raise ValueError(f"Upload duration must be between {MIN_DURATION} and {MAX_DURATION} seconds")
    
    if not MIN_CONNECTIONS <= connections <= MAX_CONNECTIONS:
        raise ValueError(f"Connections must be between {MIN_CONNECTIONS} and {MAX_CONNECTIONS}")


async def run_speedtest(
    json_output: bool = False,
    output_file: Optional[str] = None,
    simple: bool = False,
    server_id: Optional[int] = None,
    ping_count: int = 10,
    download_duration: float = 10.0,
    upload_duration: float = 10.0,
    connections: int = 4
):
    """
    Run the full speedtest sequence.
    """
    if not json_output and not simple:
        print_header()
    
    # Initialize API
    async with SpeedtestAPI() as api:
        # Get client info
        if not json_output and not simple:
            console.print("[dim]Fetching client info...[/dim]")
        
        client_info = await api.get_client_info()
        
        if not json_output and not simple:
            print_client_info(
                ip=client_info.ip,
                isp=client_info.isp,
                location=client_info.country
            )
        
        # Fetch servers
        if not json_output and not simple:
            console.print("[dim]Fetching server list...[/dim]")
        
        servers = await api.fetch_servers(limit=10)
        
        if not servers:
            console.print("[red]Error: No servers available[/red]")
            return
        
        # Filter by server ID if specified
        if server_id:
            servers = [s for s in servers if s.id == server_id]
            if not servers:
                console.print(f"[red]Error: Server {server_id} not found[/red]")
                return
        
        # Latency testing
        if not json_output and not simple:
            console.print("\n[bold]Testing latency to servers...[/bold]")
        
        latency_tester = LatencyTester(ping_count=ping_count)
        latency_results = await latency_tester.test_servers(servers)
        
        # Select best server
        successful_results = [r for r in latency_results if r.success]
        if not successful_results:
            console.print("[red]Error: Could not connect to any servers[/red]")
            return
        
        best_result = successful_results[0]
        best_server = best_result.server
        
        if not json_output and not simple:
            print_server_selection(latency_results, selected_idx=0)
            console.print(f"\n[green]Selected server:[/green] {best_server.name} ({best_server.sponsor})")
            print_latency_details(best_result)
        
        # Download test
        if not json_output and not simple:
            console.print("\n[bold]Testing download speed...[/bold]")
            progress = ProgressDisplay()
            progress.start("Downloading")
        
        download_tester = SimpleDownloadTester(duration_seconds=download_duration)
        
        if not json_output and not simple:
            download_tester.on_progress = lambda p, s: progress.update(p, s)
        
        download_result = await download_tester.test(best_server, connections=connections)
        
        if not json_output and not simple:
            progress.stop()
            print_speed_result(download_result, "Download Results", "green")
        
        # Upload test
        if not json_output and not simple:
            console.print("\n[bold]Testing upload speed...[/bold]")
            progress = ProgressDisplay()
            progress.start("Uploading")
        
        upload_tester = UploadTester(duration_seconds=upload_duration)
        
        if not json_output and not simple:
            upload_tester.on_progress = lambda p, s: progress.update(p, s)
        
        upload_result = await upload_tester.test(best_server, connections=connections)
        
        if not json_output and not simple:
            progress.stop()
            print_speed_result(upload_result, "Upload Results", "blue")
        
        # Final results
        if not json_output and not simple:
            print_final_results(
                ping_ms=best_result.latency_ms,
                jitter_ms=best_result.jitter_ms,
                download_mbps=download_result.speed_mbps,
                upload_mbps=upload_result.speed_mbps,
                server_name=best_server.name,
                server_sponsor=best_server.sponsor
            )
        elif simple:
            print(f"Ping: {best_result.latency_ms:.1f} ms")
            print(f"Download: {download_result.speed_mbps:.2f} Mbps")
            print(f"Upload: {upload_result.speed_mbps:.2f} Mbps")
        
        # Create JSON result
        result_json = create_result_json(
            client_info=client_info.to_dict(),
            server_info=best_server.to_dict(),
            latency_results=best_result.to_dict(),
            download_results=download_result.to_dict(),
            upload_results=upload_result.to_dict(),
            server_selection=[r.to_dict() for r in latency_results[:10]]
        )
        
        # Output JSON
        if json_output:
            print(json.dumps(result_json, indent=2))
        
        # Save to file
        if output_file:
            save_json(result_json, output_file)
            if not json_output:
                console.print(f"\n[green]Results saved to:[/green] {output_file}")
        
        return result_json


def main():
    parser = argparse.ArgumentParser(
        description="Speedtest CLI - Advanced network speed testing"
    )
    
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results as JSON"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        metavar="FILE",
        help="Save results to JSON file"
    )
    
    parser.add_argument(
        "--simple", "-s",
        action="store_true",
        help="Simple output mode (no dashboard)"
    )
    
    parser.add_argument(
        "--server",
        type=int,
        metavar="ID",
        help="Use specific server by ID"
    )
    
    parser.add_argument(
        "--ping-count",
        type=int,
        default=10,
        metavar="N",
        help="Number of ping samples (default: 10)"
    )
    
    parser.add_argument(
        "--download-duration",
        type=float,
        default=10.0,
        metavar="SECS",
        help="Download test duration in seconds (default: 10)"
    )
    
    parser.add_argument(
        "--upload-duration",
        type=float,
        default=10.0,
        metavar="SECS",
        help="Upload test duration in seconds (default: 10)"
    )
    
    parser.add_argument(
        "--connections",
        type=int,
        default=4,
        metavar="N",
        help="Number of concurrent connections (default: 4)"
    )
    
    parser.add_argument(
        "--list-servers",
        action="store_true",
        help="List available servers and exit"
    )
    
    args = parser.parse_args()
    
    # Validate parameters
    try:
        validate_parameters(
            ping_count=args.ping_count,
            download_duration=args.download_duration,
            upload_duration=args.upload_duration,
            connections=args.connections
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    
    # List servers mode
    if args.list_servers:
        async def list_servers():
            async with SpeedtestAPI() as api:
                servers = await api.fetch_servers(limit=20)
                console.print("\n[bold]Available Servers:[/bold]\n")
                for s in servers:
                    console.print(f"  {s.id:>6} | {s.name:<20} | {s.sponsor:<30} | {s.distance:.0f} km")
        
        asyncio.run(list_servers())
        return
    
    # Run speedtest
    try:
        asyncio.run(run_speedtest(
            json_output=args.json,
            output_file=args.output,
            simple=args.simple,
            server_id=args.server,
            ping_count=args.ping_count,
            download_duration=args.download_duration,
            upload_duration=args.upload_duration,
            connections=args.connections
        ))
    except KeyboardInterrupt:
        console.print("\n[yellow]Test cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
