"""Advanced tests for download and upload result objects and IQM calculation."""

import unittest

from client.download import DownloadResult
from client.upload import UploadResult
from client.stats import ConnectionStats, LatencyStats, calculate_iqm


class TestDownloadResultCalculate(unittest.TestCase):
    def test_basic_speed(self):
        r = DownloadResult(bytes_total=125_000_000, duration_ms=10_000)
        r.calculate()
        self.assertAlmostEqual(r.speed_mbps, 100.0)

    def test_zero_duration(self):
        r = DownloadResult(bytes_total=100, duration_ms=0)
        r.calculate()
        self.assertEqual(r.speed_mbps, 0.0)

    def test_calculate_from_samples_iqm(self):
        # IQM of [10, 20, 30, 40, 50, 60, 70, 80] is mean of [30,40,50,60] = 45
        r = DownloadResult()
        r.samples = [10, 20, 30, 40, 50, 60, 70, 80]
        r.calculate_from_samples()
        self.assertAlmostEqual(r.speed_mbps, 45.0)

    def test_calculate_from_samples_few(self):
        r = DownloadResult()
        r.samples = [100.0, 110.0]
        r.calculate_from_samples()
        self.assertAlmostEqual(r.speed_mbps, 105.0)

    def test_calculate_from_samples_empty_fallback(self):
        r = DownloadResult(bytes_total=125_000_000, duration_ms=10_000)
        r.samples = []
        r.calculate_from_samples()
        # Falls back to total/duration
        self.assertAlmostEqual(r.speed_mbps, 100.0)

    def test_to_dict_complete(self):
        r = DownloadResult(
            speed_bps=100e6, speed_mbps=100.0,
            bytes_total=125_000_000, duration_ms=10_000,
            samples=[90.0, 100.0, 110.0],
        )
        r.connections = [ConnectionStats(id=0, bytes_transferred=125_000_000, duration_ms=10_000)]
        d = r.to_dict()
        self.assertEqual(d["speed_mbps"], 100.0)
        self.assertEqual(len(d["connections"]), 1)
        self.assertEqual(len(d["samples"]), 3)
        self.assertNotIn("loaded_latency", d)

    def test_to_dict_with_loaded_latency(self):
        r = DownloadResult(speed_mbps=100.0)
        ll = LatencyStats(samples=[15.0, 20.0, 18.0])
        ll.calculate()
        r.loaded_latency = ll
        d = r.to_dict()
        self.assertIn("loaded_latency", d)
        self.assertEqual(d["loaded_latency"]["count"], 3)


class TestUploadResultCalculate(unittest.TestCase):
    def test_basic_speed(self):
        r = UploadResult(bytes_total=62_500_000, duration_ms=10_000)
        r.calculate()
        self.assertAlmostEqual(r.speed_mbps, 50.0)

    def test_calculate_from_samples_iqm(self):
        r = UploadResult()
        r.samples = [10, 20, 30, 40, 50, 60, 70, 80]
        r.calculate_from_samples()
        self.assertAlmostEqual(r.speed_mbps, 45.0)

    def test_to_dict_with_loaded_latency(self):
        r = UploadResult(speed_mbps=50.0)
        ll = LatencyStats(samples=[25.0, 30.0])
        ll.calculate()
        r.loaded_latency = ll
        d = r.to_dict()
        self.assertIn("loaded_latency", d)


class TestIqmFunction(unittest.TestCase):
    """Test the calculate_iqm helper from stats (used by download and upload)."""

    def test_empty(self):
        self.assertEqual(calculate_iqm([]), 0.0)

    def test_few(self):
        self.assertAlmostEqual(calculate_iqm([10.0, 20.0, 30.0]), 20.0)

    def test_outlier_resistant(self):
        # Extreme outliers should be trimmed
        samples = [50, 50, 50, 50, 50, 50, 500, 1]
        result = calculate_iqm(samples)
        # sorted: [1, 50, 50, 50, 50, 50, 50, 500] -> Q1=2, Q3=6 -> [50,50,50,50] = 50
        self.assertAlmostEqual(result, 50.0)

    def test_large_dataset(self):
        samples = list(range(1, 101))  # 1 to 100
        result = calculate_iqm(samples)
        # Q1=25, Q3=75 -> middle is [26..75] -> mean = 50.5
        self.assertAlmostEqual(result, 50.5)


if __name__ == "__main__":
    unittest.main()
