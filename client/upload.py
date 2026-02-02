"""
Upload speed test module.
Uses HTTPS POST to measure upload speed.
"""
import asyncio
import time
import os
import aiohttp
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from .api import Server
from .stats import ConnectionStats, LatencyStats


# Constants for upload testing
UPLOAD_CHUNK_SIZE = 256 * 1024  # 256KB chunks for better TCP window utilization
UPLOAD_BUFFER_SIZE = 1024 * 1024  # 1MB buffer for pre-generated data
SAMPLE_INTERVAL = 0.1  # 100ms sampling interval for accurate jitter calculation
MAX_CONNECTIONS = 32  # Maximum allowed concurrent connections
MIN_CONNECTIONS = 1   # Minimum allowed concurrent connections


@dataclass
class UploadResult:
    """Upload test result."""
    speed_bps: float = 0.0
    speed_mbps: float = 0.0
    bytes_total: int = 0
    duration_ms: float = 0.0
    connections: List[ConnectionStats] = field(default_factory=list)
    loaded_latency: Optional[LatencyStats] = None
    samples: List[float] = field(default_factory=list)
    
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


class UploadTester:
    """
    Upload speed tester using HTTPS POST with infinite streaming.
    Ensures test runs exactly for duration_seconds.
    """
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "Content-Type": "application/octet-stream",
        "Origin": "https://www.speedtest.net",
        "Referer": "https://www.speedtest.net/",
    }
    
    def __init__(self, duration_seconds: float = 15.0):
        self.duration_seconds = duration_seconds
        # Pre-generate larger buffer for better performance
        self._data_buffer = os.urandom(UPLOAD_BUFFER_SIZE)  # 1MB buffer
        self._chunk_size = UPLOAD_CHUNK_SIZE
        self.on_progress: Optional[Callable[[float, float], None]] = None
    
    async def test(self, server: Server, connections: int = 4) -> UploadResult:
        """Perform upload speed test."""
        # Validate connection count
        connections = max(MIN_CONNECTIONS, min(connections, MAX_CONNECTIONS))
        
        result = UploadResult()
        
        bytes_uploaded = 0
        speed_samples = []
        connection_stats = []  # Shared list to collect connection stats
        start_time = time.perf_counter()
        end_time = start_time + self.duration_seconds
        stop_flag = asyncio.Event()
        
        async def upload_worker(conn_id: int) -> ConnectionStats:
            nonlocal bytes_uploaded
            
            stats = ConnectionStats(
                id=conn_id,
                server_id=server.id,
                hostname=server.hostname
            )
            
            # Add to shared list for final collection
            connection_stats.append(stats)
            
            conn_start = time.perf_counter()
            timeout = aiohttp.ClientTimeout(total=None, connect=5, sock_read=5)
            
            # Track position in buffer for cycling through data
            buffer_pos = 0
            buffer_size = len(self._data_buffer)
            
            # Async generator that yields data until stop_flag is set
            async def data_stream():
                nonlocal bytes_uploaded, buffer_pos
                
                while not stop_flag.is_set() and time.perf_counter() < end_time:
                    # Get chunk from buffer (cycle through if needed)
                    chunk_end = buffer_pos + self._chunk_size
                    if chunk_end > buffer_size:
                        # Need to wrap around, yield two chunks
                        first_part = self._data_buffer[buffer_pos:]
                        second_part = self._data_buffer[:chunk_end - buffer_size]
                        chunk = first_part + second_part
                        buffer_pos = chunk_end - buffer_size
                    else:
                        chunk = self._data_buffer[buffer_pos:chunk_end]
                        buffer_pos = chunk_end
                    
                    chunk_len = len(chunk)
                    stats.bytes_transferred += chunk_len
                    bytes_uploaded += chunk_len
                    
                    # Small sleep to allow event loop to handle cancellations
                    # But don't sleep too much or speed drops
                    if stats.bytes_transferred % (1024*1024) == 0:  # Check every 1MB
                        await asyncio.sleep(0)
                    
                    yield chunk
                        
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
                    # We create a new POST request whenever the previous one finishes (unlikely if streaming works right)
                    # or just run one long streaming POST.
                    while not stop_flag.is_set() and time.perf_counter() < end_time:
                        try:
                            # Use chunked encoding implicitly by passing async generator
                            async with session.post(
                                server.upload_url,
                                data=data_stream()
                            ) as response:
                                await response.read()
                        except asyncio.CancelledError:
                            break
                        except (aiohttp.ClientError, OSError) as e:
                            # If connection breaks, retry if time permits
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
            nonlocal bytes_uploaded
            last_bytes = 0
            last_time = start_time
            
            while not stop_flag.is_set() and time.perf_counter() < end_time:
                try:
                    await asyncio.wait_for(stop_flag.wait(), timeout=SAMPLE_INTERVAL)
                except asyncio.TimeoutError:
                    pass
                
                current_time = time.perf_counter()
                current_bytes = bytes_uploaded
                
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
        worker_tasks = [asyncio.create_task(upload_worker(i)) for i in range(connections)]
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
        
        # Wait for tasks to complete
        await asyncio.gather(*worker_tasks, return_exceptions=True)
        try:
            await sampler_task
        except:
            pass
        
        # Collect results from shared list
        result.duration_ms = (time.perf_counter() - start_time) * 1000
        result.bytes_total = bytes_uploaded
        result.samples = speed_samples
        result.connections = connection_stats  # Use shared list populated by workers
        result.calculate()
        
        return result
