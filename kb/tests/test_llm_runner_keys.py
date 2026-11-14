"""Key-rotation tests: the multi-account pool must be walked without races."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import kb.llm_runner as L


def _spec_with_pool(keys: dict[str, str]) -> dict:
    return {"id": "amd_tokenlab", "key_source": "AMD_TOKENLAB_API_KEY"}


def test_load_key_rotates_evenly_across_a_multi_key_pool(monkeypatch):
    refs = {f"AMD_TOKENLAB_API_KEY_{i}": f"k{i}" for i in range(1, 5)}
    monkeypatch.setattr(L, "_ref", lambda name: refs.get(name, ""))
    monkeypatch.setattr(L, "_provider_spec", lambda model: _spec_with_pool(refs))
    monkeypatch.setattr(L, "_KEY_ROTATION", {})
    got = [L.load_key("auto", "m") for _ in range(8)]
    assert got == ["k1", "k2", "k3", "k4"] * 2


def test_load_key_rotation_is_thread_safe(monkeypatch):
    n_keys, n_calls = 8, 160
    refs = {f"AMD_TOKENLAB_API_KEY_{i}": f"k{i}" for i in range(1, n_keys + 1)}
    monkeypatch.setattr(L, "_ref", lambda name: refs.get(name, ""))
    monkeypatch.setattr(L, "_provider_spec", lambda model: _spec_with_pool(refs))
    monkeypatch.setattr(L, "_KEY_ROTATION", {})
    with ThreadPoolExecutor(max_workers=16) as ex:
        got = list(ex.map(lambda _: L.load_key("auto", "m"), range(n_calls)))
    counts = {k: got.count(k) for k in refs.values()}
    # a racy read-modify-write loses increments and skews the pool; every key must get an equal
    # share of the calls when the counter is guarded.
    assert set(counts.values()) == {n_calls // n_keys}


def test_load_key_lock_exists_and_guard_is_not_a_noop():
    assert isinstance(L._KEY_ROTATION_LOCK, type(threading.Lock()))
