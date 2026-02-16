import unittest
import asyncio
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.hop_monitor_service import HopMonitorService, HopStatus

class TestHopMonitorDNS(unittest.TestCase):
    def test_background_resolution(self):
        # Setup
        executor = MagicMock()
        service = HopMonitorService(executor)
        
        hop = HopStatus(hop_number=1, ip="8.8.8.8", hostname="8.8.8.8")
        
        # Trigger resolution
        service._resolve_hostname_bg(hop)
        
        # Verify executor submitted a task
        executor.submit.assert_called_once()
        
        # Extract the function submitted to executor
        submitted_func = executor.submit.call_args[0][0]
        
        # Mock socket.gethostbyaddr
        with patch('socket.gethostbyaddr') as mock_gethost:
            mock_gethost.return_value = ("dns.google", [], ["8.8.8.8"])
            
            # Execute the function (simulating thread execution)
            submitted_func()
            
            # Verify hostname updated
            self.assertEqual(hop.hostname, "dns.google")

if __name__ == "__main__":
    unittest.main()
