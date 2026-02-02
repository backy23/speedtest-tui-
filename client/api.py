"""
Speedtest.net API communication module.
Handles server discovery and configuration fetching.
"""
import aiohttp
import re
import json
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin


# Speedtest.net endpoints
BASE_URL = "https://www.speedtest.net"
CONFIG_URL = "https://www.speedtest.net/api/js/servers"


@dataclass
class Server:
    """Speedtest server information."""
    id: int
    name: str
    sponsor: str
    hostname: str
    port: int
    country: str
    cc: str
    lat: float
    lon: float
    distance: float
    url: str
    https_functional: bool = True
    
    @classmethod
    def from_dict(cls, data: dict) -> "Server":
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            sponsor=data.get("sponsor", ""),
            hostname=data.get("hostname", data.get("host", "").split(":")[0]),
            port=data.get("port", 8080),
            country=data.get("country", ""),
            cc=data.get("cc", ""),
            lat=float(data.get("lat", 0)),
            lon=float(data.get("lon", 0)),
            distance=float(data.get("distance", 0)),
            url=data.get("url", ""),
            https_functional=bool(data.get("httpsFunctional", True))
        )
    
    @property
    def ws_url(self) -> str:
        """WebSocket URL for latency testing."""
        return f"wss://{self.hostname}:{self.port}/ws?"
    
    @property
    def download_url(self) -> str:
        """HTTPS URL for download testing."""
        return f"https://{self.hostname}:{self.port}/download"
    
    @property
    def upload_url(self) -> str:
        """HTTPS URL for upload testing."""
        return f"https://{self.hostname}:{self.port}/upload"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "sponsor": self.sponsor,
            "hostname": self.hostname,
            "port": self.port,
            "country": self.country,
            "cc": self.cc,
            "lat": self.lat,
            "lon": self.lon,
            "distance": self.distance
        }


@dataclass
class ClientInfo:
    """Client information from Speedtest.net."""
    ip: str
    isp: str
    lat: float
    lon: float
    country: str
    
    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "isp": self.isp,
            "lat": self.lat,
            "lon": self.lon,
            "country": self.country
        }


class SpeedtestAPI:
    """Speedtest.net API client."""
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Origin": "https://www.speedtest.net",
        "Referer": "https://www.speedtest.net/",
    }
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.servers: List[Server] = []
        self.client_info: Optional[ClientInfo] = None
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def connect(self):
        """Create aiohttp session."""
        self.session = aiohttp.ClientSession(headers=self.HEADERS)
    
    async def close(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def fetch_config(self) -> Dict[str, Any]:
        """Fetch configuration from Speedtest.net main page."""
        async with self.session.get(BASE_URL) as response:
            html = await response.text()
        
        # Extract embedded config from HTML
        config = {}
        
        # Try to find IP and ISP info
        ip_match = re.search(r'"ipAddress"\s*:\s*"([^"]+)"', html)
        isp_match = re.search(r'"ispName"\s*:\s*"([^"]+)"', html)
        lat_match = re.search(r'"latitude"\s*:\s*([\d.]+)', html)
        lon_match = re.search(r'"longitude"\s*:\s*([\d.]+)', html)
        country_match = re.search(r'"countryCode"\s*:\s*"([^"]+)"', html)
        
        if ip_match:
            config["ip"] = ip_match.group(1)
        if isp_match:
            config["isp"] = isp_match.group(1)
        if lat_match:
            config["lat"] = float(lat_match.group(1))
        if lon_match:
            config["lon"] = float(lon_match.group(1))
        if country_match:
            config["country"] = country_match.group(1)
        
        return config
    
    async def fetch_servers(self, limit: int = 10) -> List[Server]:
        """Fetch nearby speedtest servers."""
        params = {
            "engine": "js",
            "https_functional": "true",
            "limit": str(limit)
        }
        
        async with self.session.get(CONFIG_URL, params=params) as response:
            data = await response.json()
        
        self.servers = [Server.from_dict(s) for s in data]
        return self.servers
    
    async def get_client_info(self) -> ClientInfo:
        """Get client information."""
        config = await self.fetch_config()
        
        self.client_info = ClientInfo(
            ip=config.get("ip", ""),
            isp=config.get("isp", ""),
            lat=config.get("lat", 0.0),
            lon=config.get("lon", 0.0),
            country=config.get("country", "")
        )
        
        return self.client_info
    
    async def select_best_server(self, servers: List[Server] = None) -> Server:
        """
        Select the best server based on latency.
        This should be called after latency tests are performed.
        """
        if servers is None:
            servers = self.servers
        
        if not servers:
            raise ValueError("No servers available")
        
        # For now, return the first (closest by distance) server
        # The actual selection will be done after latency testing
        return servers[0]
