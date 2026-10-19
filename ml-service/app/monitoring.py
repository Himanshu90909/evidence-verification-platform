"""In-process monitoring: latency, errors, prediction distribution.

Exposes Prometheus text format on /metrics. The web layer additionally
persists request-level audit rows in PostgreSQL (see the Prisma AuditLog).
"""
from __future__ import annotations

import threading
import time
from collections import Counter, defaultdict
from typing import Dict, List


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started_at = time.time()
        self.request_count = 0
        self.error_count = 0
        self.verdict_counter: Counter = Counter()
        self.nli_label_counter: Counter = Counter()
        self.latencies_ms: Dict[str, List[float]] = defaultdict(list)
        self._latency_sums: Dict[str, Dict[str, float]] = defaultdict(lambda: {"sum": 0.0, "count": 0, "max": 0.0})
        self.confidences: List[float] = []
        self.latency_buckets: Dict[str, Counter] = defaultdict(Counter)  # simple histogram (log-ish buckets)

    def observe_latency(self, stage: str, ms: float) -> None:
        with self._lock:
            self.latencies_ms[stage].append(ms)
            agg = self._latency_sums[stage]
            agg["sum"] += ms
            agg["count"] += 1
            agg["max"] = max(agg["max"], ms)
            for bound in (10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000):
                if ms < bound:
                    self.latency_buckets[stage][f"<{bound}ms"] += 1

    def observe_request(self, error: bool = False) -> None:
        with self._lock:
            self.request_count += 1
            if error:
                self.error_count += 1

    def observe_verdict(self, verdict: str, confidence: float, nli_label: str) -> None:
        with self._lock:
            self.verdict_counter[verdict] += 1
            self.nli_label_counter[nli_label] += 1
            self.confidences.append(confidence)

    def summary(self) -> Dict[str, object]:
        with self._lock:
            return {
                "uptime_seconds": round(time.time() - self.started_at, 1),
                "request_count": self.request_count,
                "error_count": self.error_count,
                "error_rate": (self.error_count / self.request_count) if self.request_count else 0.0,
                "verdict_distribution": dict(self.verdict_counter),
                "nli_label_distribution": dict(self.nli_label_counter),
                "mean_confidence": (sum(self.confidences) / len(self.confidences)) if self.confidences else None,
                "stage_latencies_ms": {
                    stage: {
                        "mean_ms": round(agg["sum"] / agg["count"], 2),
                        "max_ms": round(agg["max"], 2),
                        "count": agg["count"],
                    }
                    for stage, agg in self._latency_sums.items()
                },
            }

    def prometheus(self) -> str:
        s = self.summary()
        lines: List[str] = []
        lines.append("# HELP evp_requests_total Total requests")
        lines.append("# TYPE evp_requests_total counter")
        lines.append(f"evp_requests_total {s['request_count']}")
        lines.append("# HELP evp_errors_total Total errors")
        lines.append("# TYPE evp_errors_total counter")
        lines.append(f"evp_errors_total {s['error_count']}")
        for verdict, count in (s["verdict_distribution"] or {}).items():  # type: ignore[union-attr]
            lines.append(f'evp_verdicts_total{{verdict="{verdict}"}} {count}')
        for stage, agg in (s["stage_latencies_ms"] or {}).items():  # type: ignore[union-attr]
            lines.append(f'evp_stage_latency_ms{{stage="{stage}",stat="mean"}} {agg["mean_ms"]}')
            lines.append(f'evp_stage_latency_ms{{stage="{stage}",stat="max"}} {agg["max_ms"]}')
        if s["mean_confidence"] is not None:
            lines.append(f"evp_mean_confidence {s['mean_confidence']}")
        return "\n".join(lines) + "\n"


metrics = Metrics()
