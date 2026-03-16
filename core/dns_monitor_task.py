"""DNS monitoring background task."""

from __future__ import annotations

import logging

from config import (
    DNS_CHECK_INTERVAL,
    DNS_RECORD_TYPES,
    ENABLE_DNS_MONITORING,
    ENABLE_DNS_BENCHMARK,
    DNS_BENCHMARK_DOTCOM_DOMAIN,
    DNS_BENCHMARK_SERVERS,
    t,
)
from core.background_task import BackgroundTask
from services import DNSService


class DNSMonitorTask(BackgroundTask):
    """Periodically check DNS resolution and run benchmark tests."""

    def __init__(self, *, dns_service: DNSService, **kw) -> None:
        super().__init__(
            name="DNSMonitor",
            interval=DNS_CHECK_INTERVAL,
            enabled=ENABLE_DNS_MONITORING,
            **kw,
        )
        self.dns_service = dns_service

    async def execute(self) -> None:
        try:
            # Run detailed DNS check with configured record types
            # Now fully async, so we await directly
            results = await self.dns_service.check_dns_resolve(
                None,  # Use default domain
                DNS_RECORD_TYPES,
            )

            # Convert results to dict format for storage
            results_dict = [
                {
                    "record_type": r.record_type,
                    "success": r.success,
                    "response_time_ms": r.response_time_ms,
                    "status": r.status,
                    "ttl": r.ttl,
                    "records": r.records,
                    "error": r.error,
                }
                for r in results
            ]

            self.stats_repo.update_dns_detailed(results_dict)

            app_sent_bytes = len(results_dict) * 80
            app_recv_bytes = sum(
                96 + sum(len(str(record)) for record in result.get("records", []))
                for result in results_dict
                if result.get("success")
            )

            # Run benchmark tests (Cached/Uncached/DotCom)
            benchmark_dict = None  # Initialized before conditional for clarity
            if ENABLE_DNS_BENCHMARK:
                benchmark_results = await self.dns_service.run_benchmark_tests(
                    DNS_BENCHMARK_DOTCOM_DOMAIN,
                    DNS_BENCHMARK_SERVERS,
                )

                # Convert benchmark results to dict format
                benchmark_dict = [
                    {
                        "server": r.server,
                        "test_type": r.test_type,
                        "domain": r.domain,
                        "queries": r.queries,
                        "min_ms": r.min_ms,
                        "avg_ms": r.avg_ms,
                        "max_ms": r.max_ms,
                        "std_dev": r.std_dev,
                        "reliability": r.reliability,
                        "response_time_ms": r.response_time_ms,
                        "success": r.success,
                        "status": r.status,
                        "error": r.error,
                    }
                    for r in benchmark_results
                ]

                self.stats_repo.update_dns_benchmark(benchmark_dict)
                app_sent_bytes += len(benchmark_dict) * 80
                app_recv_bytes += sum(
                    96
                    for result in benchmark_dict
                    if result.get("success")
                )

            # Calculate and store DNS health metrics
            dns_health = self.dns_service.calculate_dns_health(
                results_dict,
                benchmark_dict,
            )
            self.stats_repo.update_dns_health(dns_health)
            self.stats_repo.update_app_traffic(app_sent_bytes, app_recv_bytes)

        except Exception as exc:
            logging.error(f"DNS monitor failed: {exc}")
            # Set status to failed on exception
            self.stats_repo.update_dns(None, t("failed"))
            raise
