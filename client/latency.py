"""
WebSocket-based latency measurement module.
Uses the Ookla Speedtest protocol for accurate ping/jitter measurement.
"""
import asyncio
import time
import websockets
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from .api import Server
from .stats import LatencyStats, calculate_jitter


# Constants for latency testing
DEFAULT_PING_COUNT = 10
DEFAULT_TIMEOUT = 5.0
HANDSHAKE_TIMEOUT = 2.0
MESSAGE_TIMEOUT = 0.5
MAX_CONCURRENT_TESTS = 10


@dataclass
class PingResult:
    """Result from a single ping."""
    latency_ms: float
    server_timestamp: int
    client_timestamp: float
    success: bool = True
    error: Optional[str] = None


@dataclass
class ServerLatencyResult:
    """Latency test results for a single server."""
    server: Server
    external_ip: str = ""
    pings: List[float] = field(default_factory=list)
    latency_ms: float = 0.0  # Best (min) latency
    jitter_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
    server_version: str = ""
    
    def calculate(self):
        """Calculate statistics from ping samples."""
        if self.pings:
            self.latency_ms = min(self.pings)
            self.jitter_ms = calculate_jitter(self.pings)
    
    def to_dict(self) -> dict:
        return {
            "server_id": self.server.id,
            "server_name": self.server.name,
            "sponsor": self.server.sponsor,
            "external_ip": self.external_ip,
            "pings": [round(p, 1) for p in self.pings],
            "latency_ms": round(self.latency_ms, 1),
            "jitter_ms": round(self.jitter_ms, 3),
            "success": self.success,
            "server_version": self.server_version
        }


class LatencyTester:
    """
    WebSocket-based latency tester using Ookla protocol.
    
    Protocol flow:
    1. Connect to wss://{hostname}:{port}/ws
    2. Receive: HELLO {version}
    3. Receive: YOURIP {ip}
    4. Receive: CAPABILITIES ...
    5. Send: PING {timestamp}
    6. Receive: PONG {server_timestamp}
    7. Repeat 5-6 for desired number of samples
    """
    
    WEBSOCKET_HEADERS = {
        "Origin": "https://www.speedtest.net",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }
    
    def __init__(self, ping_count: int = DEFAULT_PING_COUNT, timeout: float = DEFAULT_TIMEOUT):
        self.ping_count = ping_count
        self.timeout = timeout
    
    async def test_server(self, server: Server) -> ServerLatencyResult:
        """Test latency to a single server."""
        result = ServerLatencyResult(server=server)
        
        try:
            async with websockets.connect(
                server.ws_url,
                additional_headers=self.WEBSOCKET_HEADERS,
                ping_interval=None,
                close_timeout=2,
                open_timeout=self.timeout
            ) as ws:
                # Read initial handshake (with short timeout)
                await self._read_handshake(ws, result)
                
                # Perform ping tests
                for _ in range(self.ping_count):
                    ping_result = await self._perform_ping(ws)
                    if ping_result.success:
                        result.pings.append(ping_result.latency_ms)
                    else:
                        # If ping fails, don't kill the whole test immediately, try one more time?
                        # Or just stop.
                        break
                
                result.calculate()
                
        except asyncio.TimeoutError:
            result.success = False
            result.error = "Connection timeout"
        except (websockets.exceptions.WebSocketException, ConnectionError, OSError) as e:
            result.success = False
            result.error = str(e)
        
        return result
    
    async def _read_handshake(self, ws, result: ServerLatencyResult):
        """Read initial handshake messages from server."""
        # Try to read messages until we get what we want or timeout
        # We expect HELLO, YOURIP, CAPABILITIES
        start = time.perf_counter()
        required_found = 0
        
        while time.perf_counter() - start < HANDSHAKE_TIMEOUT:  # Max 2 seconds for handshake
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=MESSAGE_TIMEOUT)
                if msg.startswith("HELLO"):
                    parts = msg.split()
                    if len(parts) >= 2:
                        result.server_version = parts[1]
                elif msg.startswith("YOURIP"):
                    result.external_ip = msg.split()[1].strip()
                elif msg.startswith("CAPABILITIES"):
                    pass
                
                # If we got at least something, we can proceed
                required_found += 1
                if required_found >= 3:
                     break
            except asyncio.TimeoutError:
                # If we timed out waiting for handshake messages, just proceed to ping
                # Some servers might be quiet
                break
            except (websockets.exceptions.WebSocketException, ConnectionError, OSError):
                break
    
    async def _perform_ping(self, ws) -> PingResult:
        """Perform a single ping measurement."""
        # Send PING with current timestamp
        send_time = time.perf_counter() * 1000  # Convert to ms
        await ws.send(f"PING {send_time}")
        
        try:
            # Wait for PONG
            msg = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
            recv_time = time.perf_counter() * 1000
            
            if msg.startswith("PONG"):
                latency = recv_time - send_time
                parts = msg.split()
                server_ts = int(parts[1]) if len(parts) > 1 else 0
                
                return PingResult(
                    latency_ms=latency,
                    server_timestamp=server_ts,
                    client_timestamp=send_time,
                    success=True
                )
            else:
                return PingResult(
                    latency_ms=0,
                    server_timestamp=0,
                    client_timestamp=send_time,
                    success=False,
                    error=f"Unexpected response: {msg[:50]}"
                )
        except asyncio.TimeoutError:
            return PingResult(
                latency_ms=0,
                server_timestamp=0,
                client_timestamp=send_time,
                success=False,
                error="Ping timeout"
            )
    
    async def test_servers(
        self,
        servers: List[Server],
        concurrent: int = 1
    ) -> List[ServerLatencyResult]:
        """
        Test latency to multiple servers.
        
        Args:
            servers: List of servers to test
            concurrent: Number of concurrent tests (1 for sequential)
        
        Returns:
            List of ServerLatencyResult, sorted by latency
        """
        # Validate concurrent parameter
        concurrent = max(1, min(concurrent, MAX_CONCURRENT_TESTS))
        if concurrent == 1:
            # Sequential testing
            results = []
            for server in servers:
                result = await self.test_server(server)
                results.append(result)
        else:
            # Concurrent testing with semaphore
            semaphore = asyncio.Semaphore(concurrent)
            
            async def test_with_semaphore(server: Server):
                async with semaphore:
                    return await self.test_server(server)
            
            tasks = [test_with_semaphore(s) for s in servers]
            results = await asyncio.gather(*tasks)
        
        # Sort by latency (successes first, then by latency)
        results = sorted(
            results,
            key=lambda r: (not r.success, r.latency_ms if r.success else float('inf'))
        )
        
        return results
    
    def select_best_servers(
        self,
        results: List[ServerLatencyResult],
        count: int = 4
    ) -> List[Server]:
        """
        Select the best servers based on latency results.
        
        Speedtest.net typically uses 4 servers for download and 1 for upload.
        """
        successful = [r for r in results if r.success and r.pings]
        return [r.server for r in successful[:count]]
