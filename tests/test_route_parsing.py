import unittest
import sys
import os

# Add parent dir to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from route_analyzer import RouteAnalyzer

class TestRouteParsing(unittest.TestCase):
    def setUp(self):
        self.analyzer = RouteAnalyzer()

    def test_windows_tracert(self):
        # Simulate Windows output
        output = """
Tracing route to google.com [172.217.16.14]
over a maximum of 30 hops:

  1    <1 ms    <1 ms    <1 ms  192.168.1.1
  2     5 ms     4 ms     5 ms  10.0.0.1
  3     *        *        *     Request timed out.
  4    10 ms    10 ms    10 ms  172.217.16.14

Trace complete.
        """
        # Mock sys.platform to win32 for this test
        original_platform = sys.platform
        sys.platform = "win32"
        try:
            hops = self.analyzer.parse_traceroute_output(output)
            self.assertEqual(len(hops), 4)
            
            # Hop 1
            self.assertEqual(hops[0]["hop"], 1)
            self.assertEqual(hops[0]["ip"], "192.168.1.1")
            self.assertAlmostEqual(hops[0]["avg_latency"], 1.0)
            
            # Hop 3 (Timeout)
            self.assertEqual(hops[2]["hop"], 3)
            self.assertEqual(hops[2]["ip"], "*")
            self.assertTrue(hops[2]["is_timeout"])
            self.assertIsNone(hops[2]["avg_latency"])
            
        finally:
            sys.platform = original_platform

    def test_linux_traceroute(self):
        # Simulate Linux output
        output = """
traceroute to google.com (172.217.16.14), 30 hops max, 60 byte packets
 1  gateway (192.168.1.1)  0.345 ms  0.456 ms  0.567 ms
 2  10.0.0.1 (10.0.0.1)  5.123 ms  5.234 ms  5.345 ms
 3  * * *
 4  google.com (172.217.16.14)  10.123 ms  10.234 ms  10.345 ms
        """
        # Mock sys.platform to linux for this test
        original_platform = sys.platform
        sys.platform = "linux"
        try:
            hops = self.analyzer.parse_traceroute_output(output)
            self.assertEqual(len(hops), 4)
            
            # Hop 1
            self.assertEqual(hops[0]["hop"], 1)
            self.assertEqual(hops[0]["ip"], "gateway") # We capture host if present
            self.assertFalse(hops[0]["is_timeout"])
            
            # Hop 3 (Timeout)
            self.assertEqual(hops[2]["hop"], 3)
            self.assertEqual(hops[2]["ip"], "*")
            self.assertTrue(hops[2]["is_timeout"])
            
        finally:
            sys.platform = original_platform

if __name__ == "__main__":
    unittest.main()
