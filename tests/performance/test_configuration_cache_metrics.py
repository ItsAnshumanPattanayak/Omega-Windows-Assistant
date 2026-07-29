from time import perf_counter

import pytest

from omega.core.exceptions import PerformanceConfigurationError
from omega.performance import (
    BoundedLruCache,
    LocalTimingMetrics,
    PerformanceConfiguration,
)


def test_performance_configuration_defaults_are_private_and_bounded() -> None:
    value = PerformanceConfiguration()
    assert value.enabled
    assert not value.collect_local_timing_metrics
    assert not value.enable_sensitive_content_caching
    assert not value.enable_telemetry
    assert value.parser_cache_size == 256


@pytest.mark.parametrize(
    "settings",
    [
        {"unknown": 1},
        {"parser_cache_size": -1},
        {"diagnostic_runs": 2},
        {"enable_sensitive_content_caching": True},
        {"enable_telemetry": True},
        {"collect_local_timing_metrics": "yes"},
        {"parser_cache_size": 1.5},
    ],
)
def test_performance_configuration_rejects_unsafe_values(
    settings: dict[str, object],
) -> None:
    with pytest.raises(PerformanceConfigurationError):
        PerformanceConfiguration.from_mapping(settings)


def test_lru_cache_is_bounded_and_reports_eviction() -> None:
    cache: BoundedLruCache[str, int] = BoundedLruCache(2)
    cache.put("one", 1)
    cache.put("two", 2)
    assert cache.get("one") == 1
    cache.put("three", 3)
    assert cache.get("two") is None
    statistics = cache.statistics()
    assert statistics.size == 2
    assert statistics.evictions == 1
    cache.clear()
    assert cache.statistics().size == 0


def test_zero_size_cache_retains_nothing() -> None:
    cache: BoundedLruCache[str, str] = BoundedLruCache(0)
    cache.put("private", "not-retained")
    assert cache.get("private") is None
    assert cache.statistics().size == 0


def test_timing_metrics_are_disabled_by_default_and_bounded() -> None:
    disabled = LocalTimingMetrics(enabled=False, maximum_records=2)
    disabled.record("startup", perf_counter())
    assert disabled.snapshot() == ()

    enabled = LocalTimingMetrics(enabled=True, maximum_records=2)
    for operation in ("first", "second", "third"):
        enabled.record(operation, perf_counter())
    assert [item.operation for item in enabled.snapshot()] == ["second", "third"]
    with pytest.raises(ValueError):
        enabled.record("private command text", perf_counter())
