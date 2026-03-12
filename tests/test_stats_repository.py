"""Tests for StatsRepository class."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from stats_repository import StatsRepository


class TestStatsRepository:
    """Test StatsRepository functionality."""

    def test_initial_state(self) -> None:
        """Test initial state of StatsRepository."""
        repo = StatsRepository()
        stats = repo.get_stats()
        
        assert stats["total"] == 0
        assert stats["success"] == 0
        assert stats["failure"] == 0
        assert stats["consecutive_losses"] == 0
        assert stats["max_consecutive_losses"] == 0

    def test_update_after_ping_success(self) -> None:
        """Test update_after_ping with successful ping."""
        repo = StatsRepository()
        high_lat, loss = repo.update_after_ping(True, 10.5)
        
        stats = repo.get_stats()
        assert stats["total"] == 1
        assert stats["success"] == 1
        assert stats["failure"] == 0
        assert stats["last_latency_ms"] == "10.50"
        assert stats["min_latency"] == 10.5
        assert stats["max_latency"] == 10.5
        assert high_lat is False
        assert loss is False

    def test_update_after_ping_failure(self) -> None:
        """Test update_after_ping with failed ping."""
        repo = StatsRepository()
        high_lat, loss = repo.update_after_ping(False, None)
        
        stats = repo.get_stats()
        assert stats["total"] == 1
        assert stats["success"] == 0
        assert stats["failure"] == 1
        assert stats["consecutive_losses"] == 1
        assert stats["max_consecutive_losses"] == 1
        assert high_lat is False
        assert loss is False

    def test_update_after_ping_high_latency_alert(self) -> None:
        """Test update_after_ping with high latency alert."""
        repo = StatsRepository()
        high_lat, loss = repo.update_after_ping(
            True, 150.0, alert_on_high_latency=True, high_latency_threshold=100.0
        )
        
        assert high_lat is True
        assert loss is False

    def test_update_after_ping_packet_loss_alert(self) -> None:
        """Test update_after_ping with packet loss alert."""
        repo = StatsRepository()
        high_lat, loss = repo.update_after_ping(
            False, None, alert_on_packet_loss=True
        )
        
        assert high_lat is False
        assert loss is True

    def test_consecutive_losses_tracking(self) -> None:
        """Test consecutive losses tracking."""
        repo = StatsRepository()
        
        # First loss
        repo.update_after_ping(False, None)
        assert repo.get_consecutive_losses() == 1
        
        # Second loss
        repo.update_after_ping(False, None)
        assert repo.get_consecutive_losses() == 2
        
        # Success resets counter
        repo.update_after_ping(True, 10.0)
        assert repo.get_consecutive_losses() == 0

    def test_max_consecutive_losses(self) -> None:
        """Test max consecutive losses tracking."""
        repo = StatsRepository()
        
        for _ in range(3):
            repo.update_after_ping(False, None)
        
        stats = repo.get_stats()
        assert stats["max_consecutive_losses"] == 3
        
        # Success doesn't reset max
        repo.update_after_ping(True, 10.0)
        assert stats["max_consecutive_losses"] == 3

    def test_latency_statistics(self) -> None:
        """Test latency statistics calculation."""
        repo = StatsRepository()
        
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
        for lat in latencies:
            repo.update_after_ping(True, lat)
        
        stats = repo.get_stats()
        assert stats["min_latency"] == 10.0
        assert stats["max_latency"] == 50.0
        assert stats["total_latency_sum"] == 150.0

    def test_jitter_calculation(self) -> None:
        """Test jitter calculation."""
        repo = StatsRepository()
        
        # First latency - jitter should be 0
        repo.update_after_ping(True, 10.0)
        stats = repo.get_stats()
        assert stats["jitter"] == 0.0
        
        # Second latency - jitter calculated
        repo.update_after_ping(True, 20.0)
        stats = repo.get_stats()
        assert stats["jitter"] > 0.0

    def test_update_dns(self) -> None:
        """Test DNS update."""
        repo = StatsRepository()
        repo.update_dns(15.5, "ok")
        
        stats = repo.get_stats()
        assert stats["dns_resolve_time"] == 15.5
        assert stats["dns_status"] == "ok"

    def test_update_dns_detailed(self) -> None:
        """Test detailed DNS update."""
        repo = StatsRepository()
        dns_results = [
            {
                "record_type": "A",
                "success": True,
                "response_time_ms": 10.0,
                "status": "ok",
                "ttl": 300,
                "records": ["1.2.3.4"],
                "error": None,
            },
            {
                "record_type": "AAAA",
                "success": False,
                "response_time_ms": None,
                "status": "failed",
                "ttl": None,
                "records": [],
                "error": "NXDOMAIN",
            },
        ]
        
        repo.update_dns_detailed(dns_results)
        stats = repo.get_stats()
        
        assert "dns_results" in stats
        assert "A" in stats["dns_results"]
        assert stats["dns_results"]["A"]["success"] is True
        assert stats["dns_results"]["AAAA"]["success"] is False

    def test_update_dns_detailed_empty(self) -> None:
        """Test detailed DNS update with empty results."""
        repo = StatsRepository()
        repo.update_dns_detailed([])
        
        # Should not raise error
        stats = repo.get_stats()
        assert "dns_results" in stats

    def test_update_dns_benchmark(self) -> None:
        """Test DNS benchmark update."""
        repo = StatsRepository()
        benchmark_results = [
            {
                "server": "system",
                "test_type": "cached",
                "domain": "example.com",
                "queries": 5,
                "min_ms": 5.0,
                "avg_ms": 10.0,
                "max_ms": 15.0,
                "std_dev": 2.5,
                "reliability": 100.0,
                "response_time_ms": 10.0,
                "success": True,
                "status": "ok",
                "error": None,
            },
        ]
        
        repo.update_dns_benchmark(benchmark_results)
        stats = repo.get_stats()
        
        assert "dns_benchmark" in stats
        assert "cached" in stats["dns_benchmark"]
        assert stats["dns_benchmark"]["cached"]["avg_ms"] == 10.0

    def test_update_dns_benchmark_empty(self) -> None:
        """Test DNS benchmark update with empty results."""
        repo = StatsRepository()
        repo.update_dns_benchmark([])
        
        # Should not raise error
        stats = repo.get_stats()
        assert "dns_benchmark" in stats

    def test_update_dns_health(self) -> None:
        """Test DNS health update."""
        repo = StatsRepository()
        dns_health = {
            "score": 85,
            "reliability": 95.0,
            "avg_latency": 12.5,
            "jitter": 2.3,
            "records_ok": 5,
            "records_total": 6,
            "cache_efficiency": 80.0,
            "status": "good",
        }
        
        repo.update_dns_health(dns_health)
        stats = repo.get_stats()
        
        assert "dns_health" in stats
        assert stats["dns_health"]["score"] == 85
        assert stats["dns_health"]["status"] == "good"

    def test_update_dns_health_empty(self) -> None:
        """Test DNS health update with empty data."""
        repo = StatsRepository()
        repo.update_dns_health({})
        
        # Should not raise error - empty data is skipped
        stats = repo.get_stats()
        # dns_health may not be in stats if data was empty
        assert isinstance(stats, dict)

    def test_update_dns_health_missing_fields(self) -> None:
        """Test DNS health update with missing required fields."""
        repo = StatsRepository()
        dns_health = {
            "score": 85,
            # Missing reliability, records_ok, records_total, status
        }
        
        repo.update_dns_health(dns_health)
        
        # Should not raise error, but should log warning
        stats = repo.get_stats()
        # dns_health may not be in stats if validation failed
        assert isinstance(stats, dict)

    def test_update_mtu(self) -> None:
        """Test MTU update."""
        repo = StatsRepository()
        repo.update_mtu(1500, 1400, "ok")
        
        stats = repo.get_stats()
        assert stats["local_mtu"] == 1500
        assert stats["path_mtu"] == 1400
        assert stats["mtu_status"] == "ok"

    def test_update_ttl(self) -> None:
        """Test TTL update."""
        repo = StatsRepository()
        repo.update_ttl(64, 10)
        
        stats = repo.get_stats()
        assert stats["last_ttl"] == 64
        assert stats["ttl_hops"] == 10

    def test_update_public_ip(self) -> None:
        """Test public IP update."""
        repo = StatsRepository()
        repo.update_public_ip("1.2.3.4", "United States", "US")
        
        stats = repo.get_stats()
        assert stats["public_ip"] == "1.2.3.4"
        assert stats["country"] == "United States"
        assert stats["country_code"] == "US"

    def test_update_ip_change(self) -> None:
        """Test IP change update."""
        repo = StatsRepository()
        repo.update_public_ip("1.2.3.4", "United States", "US")
        repo.update_ip_change("1.2.3.4", "5.6.7.8")
        
        stats = repo.get_stats()
        assert stats["previous_ip"] == "1.2.3.4"
        assert stats["ip_change_time"] is not None

    def test_update_route(self) -> None:
        """Test route update."""
        repo = StatsRepository()
        hops = [{"hop": 1, "ip": "192.168.1.1"}, {"hop": 2, "ip": "10.0.0.1"}]
        repo.update_route(hops, problematic_hop=2, route_changed=True, diff_count=1)
        
        stats = repo.get_stats()
        assert stats["route_hops"] == hops
        assert stats["route_problematic_hop"] == 2
        assert stats["route_changed"] is True
        assert stats["route_last_diff_count"] == 1

    def test_update_problem_analysis(self) -> None:
        """Test problem analysis update."""
        repo = StatsRepository()
        repo.update_problem_analysis("high_latency", "stable", "consistent")
        
        stats = repo.get_stats()
        assert stats["current_problem_type"] == "high_latency"
        assert stats["problem_prediction"] == "stable"
        assert stats["problem_pattern"] == "consistent"

    def test_threshold_states(self) -> None:
        """Test threshold states."""
        repo = StatsRepository()
        
        # Initial state
        assert repo.get_threshold_state("high_packet_loss") is False
        
        # Update state
        repo.update_threshold_state("high_packet_loss", True)
        assert repo.get_threshold_state("high_packet_loss") is True
        
        # Update back to False
        repo.update_threshold_state("high_packet_loss", False)
        assert repo.get_threshold_state("high_packet_loss") is False

    def test_set_start_time(self) -> None:
        """Test start time setting."""
        repo = StatsRepository()
        start_time = datetime.now(timezone.utc)
        repo.set_start_time(start_time)
        
        stats = repo.get_stats()
        assert stats["start_time"] == start_time

    def test_get_snapshot(self) -> None:
        """Test get_snapshot returns immutable copy."""
        repo = StatsRepository()
        repo.update_after_ping(True, 10.0)
        
        snapshot = repo.get_snapshot()
        assert snapshot["total"] == 1
        assert snapshot["success"] == 1
        
        # Verify it's a copy, not reference
        snapshot["total"] = 999
        stats = repo.get_stats()
        assert stats["total"] == 1

    def test_recent_results(self) -> None:
        """Test recent results tracking."""
        repo = StatsRepository()
        
        # Add some results
        for ok in [True, False, True, True, False]:
            repo.update_after_ping(ok, 10.0 if ok else None)
        
        recent = repo.get_recent_results()
        assert len(recent) == 5
        assert list(recent) == [True, False, True, True, False]

    def test_cleanup_old_data(self) -> None:
        """Test cleanup of old data."""
        repo = StatsRepository()
        
        # Add many results to trigger cleanup
        for i in range(1000):
            repo.update_after_ping(True, 10.0)
        
        # Cleanup should not raise error
        cleaned = repo.cleanup_old_data()
        # cleanup_old_data returns a dict with cleanup stats
        assert isinstance(cleaned, dict)

    def test_check_memory_limit(self) -> None:
        """Test memory limit check."""
        repo = StatsRepository()
        
        # Should not exceed limit with small data
        exceeded, current_mb = repo.check_memory_limit()
        assert isinstance(exceeded, bool)
        assert current_mb is None or isinstance(current_mb, float)

    def test_trigger_alert_sound(self) -> None:
        """Test alert sound trigger."""
        repo = StatsRepository()
        
        # Should not raise error
        repo.trigger_alert_sound("loss")
        repo.trigger_alert_sound("high_latency")

    def test_add_alert(self) -> None:
        """Test adding alert."""
        repo = StatsRepository()
        repo.add_alert("Test alert", "warning")
        
        stats = repo.get_stats()
        assert len(stats["active_alerts"]) > 0
        assert stats["active_alerts"][0]["message"] == "Test alert"

    def test_clean_old_alerts(self) -> None:
        """Test cleaning old alerts."""
        repo = StatsRepository()
        repo.add_alert("Old alert", "info")
        
        # Clean should not raise error
        repo.clean_old_alerts()

    def test_update_hop_monitor(self) -> None:
        """Test hop monitor update."""
        repo = StatsRepository()
        hops = [{"hop": 1, "ip": "192.168.1.1"}]
        repo.update_hop_monitor(hops, discovering=True)
        
        stats = repo.get_stats()
        assert stats["hop_monitor_hops"] == hops
        assert stats["hop_monitor_discovering"] is True

    def test_set_latest_version(self) -> None:
        """Test latest version setting."""
        repo = StatsRepository()
        repo.set_latest_version("2.5.6", False)
        
        version, up_to_date, check_time = repo.get_latest_version_info()
        assert version == "2.5.6"
        assert up_to_date is False
        assert check_time is not None

    def test_update_mtu_hysteresis(self) -> None:
        """Test MTU hysteresis update."""
        repo = StatsRepository()
        
        # Issue
        issues, ok = repo.update_mtu_hysteresis(True)
        assert issues == 1
        assert ok == 0
        
        # Another issue
        issues, ok = repo.update_mtu_hysteresis(True)
        assert issues == 2
        assert ok == 0
        
        # OK resets issues
        issues, ok = repo.update_mtu_hysteresis(False)
        assert issues == 0
        assert ok == 1

    def test_update_route_hysteresis(self) -> None:
        """Test route hysteresis update."""
        repo = StatsRepository()
        
        # Change
        changes, ok = repo.update_route_hysteresis(True)
        assert changes == 1
        assert ok == 0
        
        # OK resets changes
        changes, ok = repo.update_route_hysteresis(False)
        assert changes == 0
        assert ok == 1

    def test_set_route_changed(self) -> None:
        """Test route changed flag."""
        repo = StatsRepository()
        repo.set_route_changed(True)
        
        assert repo.is_route_changed() is True
        
        repo.set_route_changed(False)
        assert repo.is_route_changed() is False

    def test_set_traceroute_running(self) -> None:
        """Test traceroute running state."""
        repo = StatsRepository()
        repo.set_traceroute_running(True)
        
        assert repo.is_traceroute_running() is True
        assert repo.get_last_traceroute_time() is not None
        
        repo.set_traceroute_running(False)
        assert repo.is_traceroute_running() is False

    def test_set_mtu_status_change_time(self) -> None:
        """Test MTU status change time."""
        repo = StatsRepository()
        repo.set_mtu_status_change_time()
        
        stats = repo.get_stats()
        assert stats["mtu_last_status_change"] is not None

    def test_get_mtu_status(self) -> None:
        """Test get MTU status."""
        repo = StatsRepository()
        status = repo.get_mtu_status()
        assert isinstance(status, str)
