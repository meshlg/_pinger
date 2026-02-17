from __future__ import annotations

import random
import socket
import statistics
import string
import time
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Optional, Any

import dns.resolver
import dns.rdatatype
import asyncio

from config import DNS_SLOW_THRESHOLD, DNS_TEST_DOMAIN, DNS_BENCHMARK_HISTORY_SIZE, t


@dataclass
class DNSQueryResult:
    """Result of a single DNS query."""
    success: bool
    record_type: str  # A, AAAA, CNAME, MX, TXT, NS, SOA, etc.
    domain: str
    response_time_ms: float | None
    records: list[Any]  # Parsed records (IPs, hostnames, etc.)
    ttl: int | None
    error: str | None
    status: str  # "ok", "slow", "failed"


@dataclass
class DNSBenchmarkResult:
    """Result of DNS benchmark test with server statistics."""
    server: str           # DNS server IP (e.g., 1.1.1.1, 8.8.8.8)
    test_type: str        # "cached", "uncached", "dotcom"
    domain: str
    queries: int          # Total queries made
    min_ms: float | None
    avg_ms: float | None
    max_ms: float | None
    std_dev: float | None # Standard deviation
    reliability: float    # Success rate % (0-100)
    response_time_ms: float | None  # Last response time (backward compat)
    success: bool
    status: str           # "ok", "slow", "failed"
    error: str | None


class DNSService:
    """Service for DNS resolution monitoring with multiple record types."""

    # Default record types to test
    DEFAULT_RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "TXT", "NS"]

    def __init__(self) -> None:
        self._resolver = dns.resolver.Resolver()
        self._resolver.timeout = 2.0
        self._resolver.lifetime = 2.0
        # Statistics history for each server and test type
        # {server: {test_type: deque([response_times])}}
        self._benchmark_history: dict[str, dict[str, deque[float]]] = {}
        # Success counters {server: {test_type: (success_count, total_count)}}
        self._benchmark_success: dict[str, dict[str, tuple[int, int]]] = {}

    def _get_server_ip(self) -> str:
        """Get current DNS server IP (or 'system' if using default)."""
        # For now return 'system' - can be extended to use specific servers
        return "system"

    def _update_history(self, server: str, test_type: str, response_time: float | None, success: bool) -> None:
        """Update history and success counters for server/test type."""
        # Initialize if needed
        if server not in self._benchmark_history:
            self._benchmark_history[server] = {}
            self._benchmark_success[server] = {}
        if test_type not in self._benchmark_history[server]:
            self._benchmark_history[server][test_type] = deque(maxlen=DNS_BENCHMARK_HISTORY_SIZE)
            self._benchmark_success[server][test_type] = (0, 0)
        
        # Update success counters
        success_count, total_count = self._benchmark_success[server][test_type]
        if success:
            success_count += 1
        total_count += 1
        self._benchmark_success[server][test_type] = (success_count, total_count)
        
        # Store response time only for successful queries
        if success and response_time is not None:
            self._benchmark_history[server][test_type].append(response_time)

    def _calculate_stats(self, server: str, test_type: str) -> dict[str, Any]:
        """Calculate statistics for server/test type."""
        history = self._benchmark_history.get(server, {}).get(test_type, deque())
        success_count, total_count = self._benchmark_success.get(server, {}).get(test_type, (0, 0))
        
        result = {
            "queries": total_count,
            "min_ms": None,
            "avg_ms": None,
            "max_ms": None,
            "std_dev": None,
            "reliability": 0.0 if total_count == 0 else (success_count / total_count * 100),
        }
        
        if history:
            times = list(history)
            result["min_ms"] = min(times)
            result["avg_ms"] = statistics.mean(times)
            result["max_ms"] = max(times)
            if len(times) >= 2:
                result["std_dev"] = statistics.stdev(times)
        
        return result

    async def _query_single_async(self, domain: str, record_type: str) -> DNSQueryResult:
        """Perform single DNS query asynchronously."""
        try:
            loop = asyncio.get_running_loop()
            start = time.time()
            
            # Get rdatatype enum from string
            rdtype = dns.rdatatype.from_text(record_type)
            
            # Perform query in executor to avoid blocking main loop
            answer = await loop.run_in_executor(
                None,
                lambda: self._resolver.resolve(domain, rdtype)
            )
            
            response_time = (time.time() - start) * 1000
            
            # Extract records based on type
            records = self._parse_records(answer, record_type)
            
            # Get TTL (use first record's TTL)
            ttl = answer.rrset.ttl if answer.rrset else None
            
            status = t("slow") if response_time > DNS_SLOW_THRESHOLD else t("ok")
            
            return DNSQueryResult(
                success=True,
                record_type=record_type,
                domain=domain,
                response_time_ms=response_time,
                records=records,
                ttl=ttl,
                error=None,
                status=status
            )

        except dns.resolver.NXDOMAIN:
            return DNSQueryResult(
                success=False,
                record_type=record_type,
                domain=domain,
                response_time_ms=None,
                records=[],
                ttl=None,
                error="NXDOMAIN",
                status=t("failed")
            )
        except dns.resolver.NoAnswer:
            return DNSQueryResult(
                success=False,
                record_type=record_type,
                domain=domain,
                response_time_ms=None,
                records=[],
                ttl=None,
                error="NoAnswer",
                status=t("failed")
            )
        except dns.resolver.Timeout:
            return DNSQueryResult(
                success=False,
                record_type=record_type,
                domain=domain,
                response_time_ms=None,
                records=[],
                ttl=None,
                error="Timeout",
                status=t("failed")
            )
        except Exception as exc:
            return DNSQueryResult(
                success=False,
                record_type=record_type,
                domain=domain,
                response_time_ms=None,
                records=[],
                ttl=None,
                error=str(exc),
                status=t("failed")
            )

    def _parse_records(self, answer: dns.resolver.Answer, record_type: str) -> list[Any]:
        """Parse DNS records from answer."""
        records = []
        
        for rdata in answer:
            if record_type == "A":
                records.append(str(rdata.address))
            elif record_type == "AAAA":
                records.append(str(rdata.address))
            elif record_type == "CNAME":
                records.append(str(rdata.target))
            elif record_type == "MX":
                records.append({
                    "preference": rdata.preference,
                    "exchange": str(rdata.exchange)
                })
            elif record_type == "TXT":
                # TXT records can have multiple strings
                txt_data = b"".join(rdata.strings).decode('utf-8', errors='replace')
                records.append(txt_data)
            elif record_type == "NS":
                records.append(str(rdata.target))
            elif record_type == "SOA":
                records.append({
                    "mname": str(rdata.mname),
                    "rname": str(rdata.rname),
                    "serial": rdata.serial,
                    "refresh": rdata.refresh,
                    "retry": rdata.retry,
                    "expire": rdata.expire,
                    "minimum": rdata.minimum
                })
            elif record_type == "PTR":
                records.append(str(rdata.target))
            elif record_type == "SRV":
                records.append({
                    "priority": rdata.priority,
                    "weight": rdata.weight,
                    "port": rdata.port,
                    "target": str(rdata.target)
                })
            else:
                records.append(str(rdata))
                
        return records

    async def check_dns_resolve(
        self,
        domain: str | None = None,
        record_types: list[str] | None = None
    ) -> list[DNSQueryResult]:
        """
        Check DNS resolution for multiple record types asynchronously.
        
        Args:
            domain: Domain to query (default: DNS_TEST_DOMAIN)
            record_types: List of record types (default: DEFAULT_RECORD_TYPES)
            
        Returns:
            List of DNSQueryResult for each record type
        """
        domain = domain or DNS_TEST_DOMAIN
        record_types = record_types or self.DEFAULT_RECORD_TYPES

        # Run queries in parallel
        tasks = [self._query_single_async(domain, rt) for rt in record_types]
        return await asyncio.gather(*tasks)

    # ==================== DNS Benchmark Tests ====================

    async def run_benchmark_tests(
        self,
        dotcom_domain: str = "cloudflare.com",
        servers: list[str] | None = None
    ) -> list[DNSBenchmarkResult]:
        """
        Run DNS benchmark tests asynchronously.
        """
        if servers is None:
            servers = ["system"]
        
        results = []
        
        for server in servers:
            # Cached test
            results.append(await self._test_cached_async(server))
            
            # Uncached test
            results.append(await self._test_uncached_async(server))
            
            # DotCom test
            results.append(await self._test_dotcom_async(dotcom_domain, server))
        
        return results

    async def _test_cached_async(self, server: str) -> DNSBenchmarkResult:
        """Test cached response asynchronously."""
        test_domain = DNS_TEST_DOMAIN
        record_type = "A"
        test_type = "cached"
        error_msg: str | None = None
        
        try:
            # First query - may be uncached
            await self._query_single_async(test_domain, record_type)
            
            # Second query - should be cached
            # We measure time inside _query_single_async, but we need raw time here.
            # Lets assume _query_single_async is accurate enough or re-implement simple resolve here.
            
            # Re-implementing simple resolve ensure we measure what we want
            loop = asyncio.get_running_loop()
            rdtype = dns.rdatatype.from_text(record_type)
            
            start = time.time()
            
            await loop.run_in_executor(
                None,
                lambda: self._resolver.resolve(test_domain, rdtype)
            )
            
            response_time = (time.time() - start) * 1000
            
            status = t("slow") if response_time > DNS_SLOW_THRESHOLD else t("ok")
            
            # Update history
            self._update_history(server, test_type, response_time, True)
            
        except Exception as exc:
            response_time = None
            status = t("failed")
            error_msg = str(exc)
            self._update_history(server, test_type, None, False)
        
        stats = self._calculate_stats(server, test_type)
        
        return DNSBenchmarkResult(
            server=server,
            test_type=test_type,
            domain=test_domain,
            queries=stats["queries"],
            min_ms=stats["min_ms"],
            avg_ms=stats["avg_ms"],
            max_ms=stats["max_ms"],
            std_dev=stats["std_dev"],
            reliability=stats["reliability"],
            response_time_ms=response_time,
            success=response_time is not None,
            status=status,
            error=error_msg,
        )

    async def _test_uncached_async(self, server: str) -> DNSBenchmarkResult:
        """Test uncached response asynchronously."""
        random_part = uuid.uuid4().hex[:12]
        test_domain = f"{random_part}.test.com"
        record_type = "A"
        test_type = "uncached"
        
        response_time = None
        status = t("failed")
        error = None
        success = False
        
        try:
            loop = asyncio.get_running_loop()
            rdtype = dns.rdatatype.from_text(record_type)
            start = time.time()
            try:
                await loop.run_in_executor(
                    None,
                    lambda: self._resolver.resolve(test_domain, rdtype)
                )
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                pass
            
            response_time = (time.time() - start) * 1000
            status = t("slow") if response_time > DNS_SLOW_THRESHOLD else t("ok")
            success = True
                
        except Exception as exc:
            error = str(exc)
        
        self._update_history(server, test_type, response_time, success)
        stats = self._calculate_stats(server, test_type)
        
        return DNSBenchmarkResult(
            server=server,
            test_type=test_type,
            domain=test_domain,
            queries=stats["queries"],
            min_ms=stats["min_ms"],
            avg_ms=stats["avg_ms"],
            max_ms=stats["max_ms"],
            std_dev=stats["std_dev"],
            reliability=stats["reliability"],
            response_time_ms=response_time,
            success=success,
            status=status,
            error=error
        )

    async def _test_dotcom_async(self, domain: str, server: str) -> DNSBenchmarkResult:
        """Test .com domain response asynchronously."""
        record_type = "A"
        test_type = "dotcom"
        error_msg: str | None = None
        
        try:
            loop = asyncio.get_running_loop()
            rdtype = dns.rdatatype.from_text(record_type)
            start = time.time()
            
            await loop.run_in_executor(
                None,
                lambda: self._resolver.resolve(domain, rdtype)
            )
            
            response_time = (time.time() - start) * 1000
            status = t("slow") if response_time > DNS_SLOW_THRESHOLD else t("ok")
            
            self._update_history(server, test_type, response_time, True)
            
        except Exception as exc:
            response_time = None
            status = t("failed")
            error_msg = str(exc)
            self._update_history(server, test_type, None, False)
        
        stats = self._calculate_stats(server, test_type)
        
        return DNSBenchmarkResult(
            server=server,
            test_type=test_type,
            domain=domain,
            queries=stats["queries"],
            min_ms=stats["min_ms"],
            avg_ms=stats["avg_ms"],
            max_ms=stats["max_ms"],
            std_dev=stats["std_dev"],
            reliability=stats["reliability"],
            response_time_ms=response_time,
            success=response_time is not None,
            status=status,
            error=error_msg,
        )

    # Legacy method for backward compatibility
    def check_dns_resolve_simple(
        self,
        domain: str | None = None
    ) -> tuple[bool, Optional[float], str]:
        """Simple A record check (backward compatible)."""
        # This is strictly blocking legacy, we can leave it or use asyncio.run
        # But since we changed check_dns_resolve to be async, we must update this.
        try:
            results = asyncio.run(self.check_dns_resolve(domain, ["A"]))
            if results:
                r = results[0]
                return r.success, r.response_time_ms, r.status
        except Exception:
            pass
        return False, None, t("failed")
