"""Advanced tests for CLI validation, CSV append, and edge cases."""

import os
import tempfile
import unittest

from client.constants import (
    DEFAULT_CONNECTIONS,
    DEFAULT_DURATION,
    DEFAULT_PING_COUNT,
    MAX_CONNECTIONS,
    MAX_DURATION,
    MAX_PING_COUNT,
    MIN_CONNECTIONS,
    MIN_DURATION,
    MIN_PING_COUNT,
)


class TestValidation(unittest.TestCase):
    """Test the _validate function from speedtest.py."""

    def _validate(self, **kwargs):
        # Import here to avoid triggering side effects at module level
        from speedtest import _validate
        defaults = {
            "ping_count": DEFAULT_PING_COUNT,
            "download_duration": DEFAULT_DURATION,
            "upload_duration": DEFAULT_DURATION,
            "connections": DEFAULT_CONNECTIONS,
        }
        defaults.update(kwargs)
        return _validate(**defaults)

    def test_defaults_valid(self):
        # Should not raise
        self._validate()

    def test_ping_count_too_low(self):
        with self.assertRaises(ValueError):
            self._validate(ping_count=MIN_PING_COUNT - 1)

    def test_ping_count_too_high(self):
        with self.assertRaises(ValueError):
            self._validate(ping_count=MAX_PING_COUNT + 1)

    def test_ping_count_boundaries(self):
        self._validate(ping_count=MIN_PING_COUNT)
        self._validate(ping_count=MAX_PING_COUNT)

    def test_download_duration_too_low(self):
        with self.assertRaises(ValueError):
            self._validate(download_duration=MIN_DURATION - 0.1)

    def test_download_duration_too_high(self):
        with self.assertRaises(ValueError):
            self._validate(download_duration=MAX_DURATION + 1)

    def test_upload_duration_too_low(self):
        with self.assertRaises(ValueError):
            self._validate(upload_duration=0)

    def test_connections_too_low(self):
        with self.assertRaises(ValueError):
            self._validate(connections=MIN_CONNECTIONS - 1)

    def test_connections_too_high(self):
        with self.assertRaises(ValueError):
            self._validate(connections=MAX_CONNECTIONS + 1)

    def test_connections_boundaries(self):
        self._validate(connections=MIN_CONNECTIONS)
        self._validate(connections=MAX_CONNECTIONS)


class TestCsvAppend(unittest.TestCase):
    """Test the _append_csv helper from speedtest.py."""

    def _append(self, path, **kwargs):
        from speedtest import _append_csv
        defaults = {
            "server_name": "TestServer",
            "isp": "TestISP",
            "ip": "1.2.3.4",
            "ping_ms": 15.0,
            "jitter_ms": 2.0,
            "download_mbps": 100.0,
            "upload_mbps": 50.0,
        }
        defaults.update(kwargs)
        _append_csv(path, **defaults)

    def test_creates_header_on_new_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            path = f.name
        os.unlink(path)  # ensure it doesn't exist
        try:
            self._append(path)
            with open(path) as fh:
                lines = fh.readlines()
            self.assertEqual(len(lines), 2)  # header + data row
            self.assertIn("timestamp", lines[0])
            self.assertIn("TestServer", lines[1])
        finally:
            os.unlink(path)

    def test_no_duplicate_header(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            path = f.name
        os.unlink(path)
        try:
            self._append(path)
            self._append(path)
            self._append(path)
            with open(path) as fh:
                lines = fh.readlines()
            self.assertEqual(len(lines), 4)  # 1 header + 3 data rows
            # Only first line should be header
            header_count = sum(1 for l in lines if l.startswith("timestamp"))
            self.assertEqual(header_count, 1)
        finally:
            os.unlink(path)

    def test_values_in_row(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            path = f.name
        os.unlink(path)
        try:
            self._append(path, download_mbps=200.0, upload_mbps=75.0)
            with open(path) as fh:
                lines = fh.readlines()
            self.assertIn("200.00", lines[1])
            self.assertIn("75.00", lines[1])
        finally:
            os.unlink(path)


class TestLatencyEdgeCases(unittest.TestCase):
    """Edge cases for latency result handling."""

    def test_single_ping(self):
        from client.latency import ServerLatencyResult
        from client.api import Server

        srv = Server.from_dict({"id": 1})
        r = ServerLatencyResult(server=srv, pings=[42.0], ping_attempts=1)
        r.calculate()
        self.assertAlmostEqual(r.latency_ms, 42.0)
        self.assertAlmostEqual(r.jitter_ms, 0.0)
        self.assertAlmostEqual(r.packet_loss, 0.0)

    def test_all_pings_lost(self):
        from client.latency import ServerLatencyResult
        from client.api import Server

        srv = Server.from_dict({"id": 1})
        r = ServerLatencyResult(server=srv, pings=[], ping_attempts=10)
        r.calculate()
        self.assertAlmostEqual(r.latency_ms, 0.0)
        self.assertAlmostEqual(r.packet_loss, 100.0)

    def test_to_dict_includes_packet_loss(self):
        from client.latency import ServerLatencyResult
        from client.api import Server

        srv = Server.from_dict({"id": 1})
        r = ServerLatencyResult(server=srv, pings=[10.0], ping_attempts=2)
        r.calculate()
        d = r.to_dict()
        self.assertIn("packet_loss", d)
        self.assertAlmostEqual(d["packet_loss"], 50.0)


class TestConnectionStatsEdgeCases(unittest.TestCase):
    def test_zero_bytes(self):
        from client.stats import ConnectionStats
        cs = ConnectionStats(bytes_transferred=0, duration_ms=1000)
        cs.calculate()
        self.assertAlmostEqual(cs.speed_mbps, 0.0)

    def test_to_dict_complete(self):
        from client.stats import ConnectionStats
        cs = ConnectionStats(id=3, server_id=99, hostname="a.b.c", bytes_transferred=1000, duration_ms=100)
        cs.calculate()
        d = cs.to_dict()
        self.assertEqual(d["id"], 3)
        self.assertEqual(d["server_id"], 99)
        self.assertGreater(d["speed_mbps"], 0)


class TestLatencyStatsEdgeCases(unittest.TestCase):
    def test_single_sample(self):
        from client.stats import LatencyStats
        ls = LatencyStats(samples=[50.0])
        ls.calculate()
        self.assertAlmostEqual(ls.min, 50.0)
        self.assertAlmostEqual(ls.max, 50.0)
        self.assertAlmostEqual(ls.mean, 50.0)
        self.assertAlmostEqual(ls.jitter, 0.0)

    def test_two_samples(self):
        from client.stats import LatencyStats
        ls = LatencyStats(samples=[10.0, 20.0])
        ls.calculate()
        self.assertAlmostEqual(ls.jitter, 10.0)

    def test_large_variance(self):
        from client.stats import LatencyStats
        ls = LatencyStats(samples=[1.0, 100.0, 1.0, 100.0])
        ls.calculate()
        self.assertGreater(ls.jitter, 50.0)


class TestConstants(unittest.TestCase):
    """Verify constants are sane."""

    def test_min_less_than_max(self):
        self.assertLess(MIN_PING_COUNT, MAX_PING_COUNT)
        self.assertLess(MIN_DURATION, MAX_DURATION)
        self.assertLess(MIN_CONNECTIONS, MAX_CONNECTIONS)

    def test_defaults_in_range(self):
        self.assertTrue(MIN_PING_COUNT <= DEFAULT_PING_COUNT <= MAX_PING_COUNT)
        self.assertTrue(MIN_DURATION <= DEFAULT_DURATION <= MAX_DURATION)
        self.assertTrue(MIN_CONNECTIONS <= DEFAULT_CONNECTIONS <= MAX_CONNECTIONS)


if __name__ == "__main__":
    unittest.main()
