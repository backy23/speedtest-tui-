"""
Download speed test module.
Uses parallel HTTPS connections to measure download speed.
"""
import asyncio
import time
import aiohttp
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from .api import Server
from .stats import SpeedStats, ConnectionStats, LatencyStats


# Constants for download testing
DOWNLOAD_CHUNK_SIZE = 256 * 1024  # 256KB chunks for better TCP window utilization
DOWNLOAD_FILE_SIZE = 50 * 1000 * 1000  # 50MB file size
SAMPLE_INTERVAL = 0.1  # 100ms sampling interval for accurate jitter calculation
MAX_CONNECTIONS = 32  # Maximum allowed concurrent connections
MIN_CONNECTIONS = 1   # Minimum allowed concurrent connections


@dataclass
class DownloadResult:
    """Download test result."""
    speed_bps: float = 0.0
    speed_mbps: float = 0.0
    bytes_total: int = 0
    duration_ms: float = 0.0
    connections: List[ConnectionStats] = field(default_factory=list)
    loaded_latency: Optional[LatencyStats] = None
    samples: List[float] = field(default_factory=list)  # Speed samples over time
    
    def calculate(self):
        """Calculate final speed."""
        if self.duration_ms > 0:
            self.speed_bps = (self.bytes_total * 8) / (self.duration_ms / 1000)
            self.speed_mbps = self.speed_bps / 1_000_000
    
    def to_dict(self) -> dict:
        result = {
            "speed_bps": round(self.speed_bps, 2),
            "speed_mbps": round(self.speed_mbps, 2),
            "bytes_total": self.bytes_total,
            "duration_ms": round(self.duration_ms, 2),
            "connections": [c.to_dict() for c in self.connections],
            "samples": [round(s, 2) for s in self.samples]
        }
        if self.loaded_latency:
            result["loaded_latency"] = self.loaded_latency.to_dict()
        return result


class DownloadTester:
    """
    Parallel download speed tester.
    Legacy implementation maintained for compatibility.
    """
    def __init__(self, duration_seconds: float = 15.0, connections_per_server: int = 4, chunk_size: int = DOWNLOAD_CHUNK_SIZE):
        self.duration_seconds = duration_seconds
        self.connections_per_server = connections_per_server
        self.chunk_size = chunk_size
        self.on_progress = None

    async def test(self, servers: List[Server], max_connections: int = 8) -> DownloadResult:
        # Redirect to SimpleDownloadTester logic for now as it is more robust
        simple = SimpleDownloadTester(self.duration_seconds)
        simple.on_progress = self.on_progress
        if servers:
            return await simple.test(servers[0], max_connections)
        return DownloadResult()


class SimpleDownloadTester:
    """
    Simplified download tester for faster results.
    Uses fewer connections and shorter duration.
    Optimized for strict timeout handling.
    """
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Origin": "https://www.speedtest.net",
        "Referer": "https://www.speedtest.net/",
    }
    
    def __init__(self, duration_seconds: float = 10.0):
        self.duration_seconds = duration_seconds
        self.on_progress: Optional[Callable[[float, float], None]] = None
    
    async def test(self, server: Server, connections: int = 4) -> DownloadResult:
        """Perform download test on a single server."""
        # Validate connection count
        connections = max(MIN_CONNECTIONS, min(connections, MAX_CONNECTIONS))
        
        result = DownloadResult()
        
        bytes_downloaded = 0
        speed_samples = []
        start_time = time.perf_counter()
        end_time = start_time + self.duration_seconds
        stop_flag = asyncio.Event()
        
        async def download_worker(conn_id: int) -> ConnectionStats:
            nonlocal bytes_downloaded
            
            stats = ConnectionStats(
                id=conn_id,
                server_id=server.id,
                hostname=server.hostname
            )
            
            conn_start = time.perf_counter()
            # Stricter timeouts: connect in 5s, read in 5s (but we read chunks so it should be fast)
            timeout = aiohttp.ClientTimeout(total=None, connect=5, sock_read=5)
            
            try:
                # Use connection pooling with force_close=False for better performance
                connector = aiohttp.TCPConnector(
                    ssl=True,
                    force_close=False,
                    limit=1,
                    limit_per_host=1,
                    enable_cleanup_closed=True
                )
                async with aiohttp.ClientSession(
                    headers=self.HEADERS,
                    connector=connector,
                    timeout=timeout
                ) as session:
                    while not stop_flag.is_set() and time.perf_counter() < end_time:
                        try:
                            url = f"{server.download_url}?size={DOWNLOAD_FILE_SIZE}"  # Use constant
                            async with session.get(url) as response:
                                while not stop_flag.is_set():
                                    try:
                                        if stop_flag.is_set() or time.perf_counter() >= end_time:
                                            break
                                            
                                        # Use wait_for to allow cancellation during potentially slow reads
                                        # Read larger chunks (256KB) for better TCP window utilization
                                        chunk = await asyncio.wait_for(response.content.read(DOWNLOAD_CHUNK_SIZE), timeout=0.5)
                                        if not chunk:
                                            break
                                        
                                        chunk_size = len(chunk)
                                        stats.bytes_transferred += chunk_size
                                        bytes_downloaded += chunk_size
                                        
                                    except asyncio.TimeoutError:
                                        # Just a check for end_time/stop_flag
                                        continue
                                    except aiohttp.ClientPayloadError as e:
                                        # Payload error, break out of inner loop
                                        break
                                    except (aiohttp.ClientError, OSError) as e:
                                        # Connection error, break out of inner loop
                                        break
                        except asyncio.CancelledError:
                            break
                        except (aiohttp.ClientError, OSError) as e:
                            # Connection error, retry if time permits
                            if stop_flag.is_set():
                                break
                            await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                pass
            except (aiohttp.ClientError, OSError) as e:
                # Connection-level error, stats will be incomplete
                pass
            
            stats.duration_ms = (time.perf_counter() - conn_start) * 1000
            stats.calculate()
            return stats
        
        async def sample_speed():
            nonlocal bytes_downloaded
            last_bytes = 0
            last_time = start_time
            
            while not stop_flag.is_set() and time.perf_counter() < end_time:
                try:
                    await asyncio.wait_for(stop_flag.wait(), timeout=SAMPLE_INTERVAL)
                    # If we woke up because stop_flag is set, loop checks and exits
                except asyncio.TimeoutError:
                    # Timeout means SAMPLE_INTERVAL passed, time to sample
                    pass
                
                current_time = time.perf_counter()
                current_bytes = bytes_downloaded
                
                elapsed = current_time - last_time
                if elapsed > 0:
                    speed_mbps = ((current_bytes - last_bytes) * 8) / elapsed / 1_000_000
                    speed_samples.append(speed_mbps)
                    
                    if self.on_progress:
                        prog = (current_time - start_time) / self.duration_seconds
                        self.on_progress(min(prog, 1.0), speed_mbps)
                
                last_bytes = current_bytes
                last_time = current_time
        
        # Create tasks
        worker_tasks = [asyncio.create_task(download_worker(i)) for i in range(connections)]
        sampler_task = asyncio.create_task(sample_speed())
        
        # Wait for duration
        remaining = end_time - time.perf_counter()
        if remaining > 0:
            await asyncio.sleep(remaining)
        
        # Signal stop
        stop_flag.set()
        
        # Cancel all tasks
        for task in worker_tasks:
            task.cancel()
        sampler_task.cancel()
        
        # Wait for tasks to complete cleanly
        results = await asyncio.gather(*worker_tasks, return_exceptions=True)
        try:
            await sampler_task
        except:
            pass
        
        connection_stats = []
        for r in results:
            if isinstance(r, ConnectionStats):
                connection_stats.append(r)
        
        result.duration_ms = (time.perf_counter() - start_time) * 1000
        result.bytes_total = bytes_downloaded
        result.connections = connection_stats
        result.samples = speed_samples
        result.calculate()
        
        return result
