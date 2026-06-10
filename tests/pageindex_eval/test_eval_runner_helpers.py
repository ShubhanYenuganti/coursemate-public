import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'api'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from eval_runner import _iteration_count, _latency_percentiles


def test_iteration_count_counts_tool_entries():
    trace = [
        {"tool": "get_material_structure", "args": {}, "iteration": 0},
        {"tool": "get_page_content", "args": {}, "iteration": 1},
        {"iteration": 2, "finish_reason": "stop", "tool_calls": 0, "latency_ms": 800},
    ]
    assert _iteration_count(trace) == 2


def test_iteration_count_empty():
    assert _iteration_count([]) == 0


def test_latency_percentiles_basic():
    values = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000]
    out = _latency_percentiles(values)
    assert out["p50"] == 5500
    assert out["p95"] == 9550
    assert out["max"] == 10000


def test_latency_percentiles_empty():
    out = _latency_percentiles([])
    assert out == {"p50": 0, "p95": 0, "max": 0}


def test_latency_percentiles_single():
    out = _latency_percentiles([1234])
    assert out["p50"] == 1234
    assert out["p95"] == 1234
    assert out["max"] == 1234
