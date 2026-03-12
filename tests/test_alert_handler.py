"""Tests for core/alert_handler.py."""
from __future__ import annotations

import pytest
from unittest.mock import Mock, MagicMock, patch
from core.alert_handler import AlertHandler
from core.ping_handler import PingResult
from stats_repository import StatsRepository


class TestAlertHandler:
    """Test AlertHandler class."""

    def test_initialization(self) -> None:
        """Test AlertHandler initialization."""
        stats_repo = Mock(spec=StatsRepository)
        handler = AlertHandler(stats_repo)
        
        assert handler.stats_repo == stats_repo
        assert handler.traceroute_service is None
        assert handler.smart_alert_manager is None

    def test_initialization_with_traceroute(self) -> None:
        """Test AlertHandler initialization with traceroute service."""
        stats_repo = Mock(spec=StatsRepository)
        traceroute_service = Mock()
        handler = AlertHandler(stats_repo, traceroute_service=traceroute_service)
        
        assert handler.traceroute_service == traceroute_service

    def test_initialization_with_smart_alert_manager(self) -> None:
        """Test AlertHandler initialization with smart alert manager."""
        stats_repo = Mock(spec=StatsRepository)
        smart_alert_manager = Mock()
        handler = AlertHandler(stats_repo, smart_alert_manager=smart_alert_manager)
        
        assert handler.smart_alert_manager == smart_alert_manager

    def test_process_alerts_no_triggers(self) -> None:
        """Test process_alerts with no alerts triggered."""
        stats_repo = Mock(spec=StatsRepository)
        handler = AlertHandler(stats_repo)
        
        ping_result = PingResult(success=True, latency=10.0, target="1.1.1.1")
        
        # Should not raise error
        handler.process_alerts(ping_result, high_latency_triggered=False, packet_loss_triggered=False)

    def test_process_alerts_high_latency(self) -> None:
        """Test process_alerts with high latency alert."""
        stats_repo = Mock(spec=StatsRepository)
        handler = AlertHandler(stats_repo)
        
        ping_result = PingResult(success=True, latency=150.0, target="1.1.1.1")
        
        with patch.object(handler, '_is_quiet_hours', return_value=False):
            handler.process_alerts(ping_result, high_latency_triggered=True, packet_loss_triggered=False)
            
            # Should trigger alert sound
            stats_repo.trigger_alert_sound.assert_called_once_with("high_latency")

    def test_process_alerts_packet_loss(self) -> None:
        """Test process_alerts with packet loss alert."""
        stats_repo = Mock(spec=StatsRepository)
        handler = AlertHandler(stats_repo)
        
        ping_result = PingResult(success=False, latency=None, target="1.1.1.1")
        
        with patch.object(handler, '_is_quiet_hours', return_value=False):
            handler.process_alerts(ping_result, high_latency_triggered=False, packet_loss_triggered=True)
            
            # Should trigger alert sound
            stats_repo.trigger_alert_sound.assert_called_once_with("loss")

    def test_process_alerts_quiet_hours(self) -> None:
        """Test process_alerts during quiet hours."""
        stats_repo = Mock(spec=StatsRepository)
        handler = AlertHandler(stats_repo)
        
        ping_result = PingResult(success=True, latency=150.0, target="1.1.1.1")
        
        with patch.object(handler, '_is_quiet_hours', return_value=True):
            handler.process_alerts(ping_result, high_latency_triggered=True, packet_loss_triggered=False)
            
            # Should not trigger alert sound during quiet hours
            stats_repo.trigger_alert_sound.assert_not_called()

    def test_is_quiet_hours_disabled(self) -> None:
        """Test _is_quiet_hours when quiet hours are disabled."""
        stats_repo = Mock(spec=StatsRepository)
        handler = AlertHandler(stats_repo)
        
        with patch('config.ENABLE_QUIET_HOURS', False):
            result = handler._is_quiet_hours()
            assert result is False

    def test_is_quiet_hours_enabled_normal_range(self) -> None:
        """Test _is_quiet_hours with normal time range."""
        stats_repo = Mock(spec=StatsRepository)
        handler = AlertHandler(stats_repo)
        
        with patch('config.ENABLE_QUIET_HOURS', True), \
             patch('config.QUIET_HOURS_START', "22:00"), \
             patch('config.QUIET_HOURS_END', "08:00"), \
             patch('core.alert_handler.datetime') as mock_datetime:
            
            # Mock current time to be within quiet hours (23:00)
            mock_datetime.now.return_value = Mock(hour=23, minute=0)
            
            result = handler._is_quiet_hours()
            assert result is True

    def test_is_quiet_hours_enabled_outside_range(self) -> None:
        """Test _is_quiet_hours outside quiet hours range."""
        stats_repo = Mock(spec=StatsRepository)
        handler = AlertHandler(stats_repo)
        
        with patch('config.ENABLE_QUIET_HOURS', True), \
             patch('config.QUIET_HOURS_START', "22:00"), \
             patch('config.QUIET_HOURS_END', "08:00"), \
             patch('core.alert_handler.datetime') as mock_datetime:
            
            # Mock current time to be outside quiet hours (12:00)
            mock_datetime.now.return_value = Mock(hour=12, minute=0)
            
            result = handler._is_quiet_hours()
            assert result is False

    def test_is_quiet_hours_wraps_midnight(self) -> None:
        """Test _is_quiet_hours with time range wrapping midnight."""
        stats_repo = Mock(spec=StatsRepository)
        handler = AlertHandler(stats_repo)
        
        with patch('config.ENABLE_QUIET_HOURS', True), \
             patch('config.QUIET_HOURS_START', "22:00"), \
             patch('config.QUIET_HOURS_END', "08:00"), \
             patch('core.alert_handler.datetime') as mock_datetime:
            
            # Mock current time to be after midnight (02:00)
            mock_datetime.now.return_value = Mock(hour=2, minute=0)
            
            result = handler._is_quiet_hours()
            assert result is True

    def test_check_auto_traceroute_disabled(self) -> None:
        """Test _check_auto_traceroute when disabled."""
        stats_repo = Mock(spec=StatsRepository)
        handler = AlertHandler(stats_repo)
        
        with patch('core.alert_handler.ENABLE_AUTO_TRACEROUTE', False):
            handler._check_auto_traceroute()
            # Should not call anything

    def test_check_auto_traceroute_no_service(self) -> None:
        """Test _check_auto_traceroute without traceroute service."""
        stats_repo = Mock(spec=StatsRepository)
        handler = AlertHandler(stats_repo)
        
        with patch('core.alert_handler.ENABLE_AUTO_TRACEROUTE', True):
            handler._check_auto_traceroute()
            # Should not call anything

    def test_check_auto_traceroute_triggered(self) -> None:
        """Test _check_auto_traceroute when triggered."""
        stats_repo = StatsRepository()
        # Set consecutive_losses to 5 by simulating failed pings
        for _ in range(5):
            stats_repo.update_after_ping(False, None)
        
        traceroute_service = Mock()
        handler = AlertHandler(stats_repo, traceroute_service=traceroute_service)
        
        # Patch constants in the module where they are used (already imported)
        # TARGET_IP is imported inside the function, so patch it in config module
        with patch('core.alert_handler.ENABLE_AUTO_TRACEROUTE', True), \
             patch('core.alert_handler.TRACEROUTE_TRIGGER_LOSSES', 3), \
             patch('config.TARGET_IP', "1.1.1.1"):
            
            handler._check_auto_traceroute()
            
            # Should trigger traceroute
            traceroute_service.trigger_traceroute.assert_called_once_with("1.1.1.1")

    def test_check_auto_traceroute_not_triggered(self) -> None:
        """Test _check_auto_traceroute when not triggered."""
        stats_repo = StatsRepository()
        # Set consecutive_losses to 2 (below threshold of 3)
        for _ in range(2):
            stats_repo.update_after_ping(False, None)
        
        traceroute_service = Mock()
        handler = AlertHandler(stats_repo, traceroute_service=traceroute_service)
        
        # Patch constants in the module where they are used (already imported)
        with patch('core.alert_handler.ENABLE_AUTO_TRACEROUTE', True), \
             patch('core.alert_handler.TRACEROUTE_TRIGGER_LOSSES', 3):
            
            handler._check_auto_traceroute()
            
            # Should not trigger traceroute
            traceroute_service.trigger_traceroute.assert_not_called()

    def test_process_legacy_alerts_high_latency(self) -> None:
        """Test _process_legacy_alerts with high latency."""
        stats_repo = Mock(spec=StatsRepository)
        handler = AlertHandler(stats_repo)
        
        with patch.object(handler, '_is_quiet_hours', return_value=False):
            handler._process_legacy_alerts(high_latency_triggered=True, packet_loss_triggered=False)
            
            stats_repo.trigger_alert_sound.assert_called_once_with("high_latency")

    def test_process_legacy_alerts_packet_loss(self) -> None:
        """Test _process_legacy_alerts with packet loss."""
        stats_repo = Mock(spec=StatsRepository)
        handler = AlertHandler(stats_repo)
        
        with patch.object(handler, '_is_quiet_hours', return_value=False), \
             patch.object(handler, '_check_auto_traceroute') as mock_check:
            
            handler._process_legacy_alerts(high_latency_triggered=False, packet_loss_triggered=True)
            
            stats_repo.trigger_alert_sound.assert_called_once_with("loss")
            mock_check.assert_called_once()

    def test_process_legacy_alerts_both(self) -> None:
        """Test _process_legacy_alerts with both alerts."""
        stats_repo = Mock(spec=StatsRepository)
        handler = AlertHandler(stats_repo)
        
        with patch.object(handler, '_is_quiet_hours', return_value=False), \
             patch.object(handler, '_check_auto_traceroute') as mock_check:
            
            handler._process_legacy_alerts(high_latency_triggered=True, packet_loss_triggered=True)
            
            # Should trigger both sounds
            assert stats_repo.trigger_alert_sound.call_count == 2
            mock_check.assert_called_once()

    def test_process_legacy_alerts_quiet_hours(self) -> None:
        """Test _process_legacy_alerts during quiet hours."""
        stats_repo = Mock(spec=StatsRepository)
        handler = AlertHandler(stats_repo)
        
        with patch.object(handler, '_is_quiet_hours', return_value=True), \
             patch.object(handler, '_check_auto_traceroute') as mock_check:
            
            handler._process_legacy_alerts(high_latency_triggered=True, packet_loss_triggered=True)
            
            # Should not trigger sounds during quiet hours
            stats_repo.trigger_alert_sound.assert_not_called()
            # But should still check auto traceroute
            mock_check.assert_called_once()
