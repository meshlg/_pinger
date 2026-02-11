"""
Alert deduplication system.

Provides fingerprint-based deduplication with time-window caching
and similarity detection to reduce duplicate alerts.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from core.alert_types import AlertEntity, AlertGroup


@dataclass
class DedupCacheEntry:
    """Entry in deduplication cache."""
    
    alert: AlertEntity
    first_seen: float
    last_seen: float
    count: int = 1
    
    def is_expired(self, window_seconds: float) -> bool:
        """Check if entry has expired."""
        return (time.time() - self.last_seen) > window_seconds
    
    def update(self) -> None:
        """Update entry with new occurrence."""
        self.last_seen = time.time()
        self.count += 1


class AlertDeduplicator:
    """
    Deduplicate alerts based on fingerprints and time windows.
    
    Reduces alert noise by suppressing duplicate alerts within a configurable
    time window. Uses alert fingerprints for exact matching and optionally
    similarity detection for fuzzy matching.
    """
    
    def __init__(
        self,
        window_seconds: int = 300,
        similarity_threshold: float = 0.85,
        enable_similarity: bool = True,
    ):
        """
        Initialize deduplicator.
        
        Args:
            window_seconds: Time window for deduplication (default: 5 minutes)
            similarity_threshold: Threshold for similarity detection (0-1)
            enable_similarity: Whether to use similarity detection
        """
        self.window_seconds = window_seconds
        self.similarity_threshold = similarity_threshold
        self.enable_similarity = enable_similarity
        
        # Cache: fingerprint -> DedupCacheEntry
        self._cache: Dict[str, DedupCacheEntry] = {}
        
        # Track suppressed alerts count
        self._suppressed_count = 0
    
    def should_suppress(self, alert: AlertEntity) -> bool:
        """
        Check if alert should be suppressed as duplicate.
        
        Args:
            alert: Alert to check
            
        Returns:
            True if alert should be suppressed, False otherwise
        """
        # Clean expired entries first
        self._cleanup_expired()
        
        fingerprint = alert.fingerprint
        
        # Check exact match by fingerprint
        if fingerprint in self._cache:
            entry = self._cache[fingerprint]
            
            # Update existing entry
            entry.update()
            self._suppressed_count += 1
            
            return True
        
        # Check similarity if enabled
        if self.enable_similarity:
            similar_entry = self._find_similar(alert)
            if similar_entry:
                # Treat as duplicate
                similar_entry.update()
                self._suppressed_count += 1
                return True
        
        # Not a duplicate - add to cache
        self._cache[fingerprint] = DedupCacheEntry(
            alert=alert,
            first_seen=time.time(),
            last_seen=time.time(),
        )
        
        return False
    
    def get_or_create_group(self, alert: AlertEntity) -> Optional[str]:
        """
        Get existing group ID for alert if it's a duplicate.
        
        Args:
            alert: Alert to check
            
        Returns:
            Group ID if alert matches existing cached alert, None otherwise
        """
        fingerprint = alert.fingerprint
        
        if fingerprint in self._cache:
            cached_alert = self._cache[fingerprint].alert
            return cached_alert.group_id
        
        return None
    
    def _find_similar(self, alert: AlertEntity) -> Optional[DedupCacheEntry]:
        """
        Find similar alert in cache using similarity detection.
        
        Uses string similarity on messages and context matching.
        
        Args:
            alert: Alert to find similar for
            
        Returns:
            Similar cache entry if found, None otherwise
        """
        for entry in self._cache.values():
            cached = entry.alert
            
            # Must have same type and context
            if (
                cached.alert_type != alert.alert_type
                or not cached.context.matches(alert.context)
            ):
                continue
            
            # Check message similarity
            similarity = self._calculate_similarity(
                alert.message,
                cached.message
            )
            
            if similarity >= self.similarity_threshold:
                return entry
        
        return None
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings.
        
        Uses Jaccard similarity based on word sets for performance.
        For more accuracy, could use Levenshtein distance.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score 0-1, where 1 is identical
        """
        if str1 == str2:
            return 1.0
        
        # Jaccard similarity on word sets
        words1 = set(str1.lower().split())
        words2 = set(str2.lower().split())
        
        if not words1 and not words2:
            return 1.0
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries from cache."""
        expired_keys = [
            fp
            for fp, entry in self._cache.items()
            if entry.is_expired(self.window_seconds)
        ]
        
        for key in expired_keys:
            del self._cache[key]
    
    def get_suppressed_count(self) -> int:
        """Get total count of suppressed alerts."""
        return self._suppressed_count
    
    def get_cache_size(self) -> int:
        """Get current cache size."""
        return len(self._cache)
    
    def get_duplicate_counts(self) -> Dict[str, int]:
        """
        Get count of duplicates for each fingerprint.
        
        Returns:
            Dictionary mapping fingerprint to duplicate count
        """
        return {
            fp: entry.count
            for fp, entry in self._cache.items()
        }
    
    def clear(self) -> None:
        """Clear all cache and reset counters."""
        self._cache.clear()
        self._suppressed_count = 0
