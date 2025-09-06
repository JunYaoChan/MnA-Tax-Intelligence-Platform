import time
import asyncio
from typing import Dict, List, Any
from collections import deque
from datetime import datetime, timedelta
import statistics

class MetricsCollector:
    """Collects and manages system metrics"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.response_times = deque(maxlen=window_size)
        self.confidence_scores = deque(maxlen=window_size)
        self.success_count = 0
        self.failure_count = 0
        self.total_queries = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.agent_usage = {}
        self.start_time = time.time()
        
    async def record_query(
        self,
        response_time: float,
        confidence: float,
        success: bool,
        agents_used: List[str],
        cache_hit: bool = False
    ):
        """Record metrics for a query"""
        self.response_times.append(response_time)
        self.confidence_scores.append(confidence)
        
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        
        self.total_queries += 1
        
        if cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
        
        # Track agent usage
        for agent in agents_used:
            self.agent_usage[agent] = self.agent_usage.get(agent, 0) + 1
    
    async def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return {
            'avg_response_time': statistics.mean(self.response_times) if self.response_times else 0,
            'median_response_time': statistics.median(self.response_times) if self.response_times else 0,
            'p95_response_time': self._calculate_percentile(self.response_times, 95),
            'p99_response_time': self._calculate_percentile(self.response_times, 99),
            'success_rate': self.success_count / max(self.total_queries, 1),
            'total_queries': self.total_queries,
            'avg_confidence': statistics.mean(self.confidence_scores) if self.confidence_scores else 0,
            'active_agents': len(self.agent_usage),
            'cache_hit_rate': self.cache_hits / max(self.cache_hits + self.cache_misses, 1),
            'uptime_seconds': time.time() - self.start_time
        }
    
    async def get_detailed_metrics(self) -> Dict[str, Any]:
        """Get detailed metrics including breakdowns"""
        base_metrics = await self.get_current_metrics()
        
        # Add detailed breakdowns
        base_metrics['agent_breakdown'] = self.agent_usage
        base_metrics['response_time_histogram'] = self._create_histogram(self.response_times)
        base_metrics['confidence_histogram'] = self._create_histogram(self.confidence_scores)
        base_metrics['queries_per_minute'] = self._calculate_qpm()
        
        return base_metrics
    
    def _calculate_percentile(self, data: deque, percentile: int) -> float:
        """Calculate percentile from data"""
        if not data:
            return 0
        
        sorted_data = sorted(data)
        index = int(len(sorted_data) * (percentile / 100))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def _create_histogram(self, data: deque, bins: int = 10) -> Dict[str, int]:
        """Create histogram from data"""
        if not data:
            return {}
        
        min_val = min(data)
        max_val = max(data)
        bin_width = (max_val - min_val) / bins if max_val > min_val else 1
        
        histogram = {}
        for i in range(bins):
            bin_start = min_val + i * bin_width
            bin_end = bin_start + bin_width
            count = sum(1 for x in data if bin_start <= x < bin_end)
            histogram[f"{bin_start:.2f}-{bin_end:.2f}"] = count
        
        return histogram
    
    def _calculate_qpm(self) -> float:
        """Calculate queries per minute"""
        uptime_minutes = (time.time() - self.start_time) / 60
        return self.total_queries / max(uptime_minutes, 1)
    
    async def reset(self):
        """Reset all metrics"""
        self.response_times.clear()
        self.confidence_scores.clear()
        self.success_count = 0
        self.failure_count = 0
        self.total_queries = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.agent_usage.clear()
        self.start_time = time.time()
