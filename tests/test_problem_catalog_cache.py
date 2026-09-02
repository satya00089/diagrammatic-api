"""Tests for the problem catalog count cache-aside boundary."""

from threading import Event, Lock, Thread

from app.services.problem_catalog_cache import ProblemCatalogCountCache


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.writes: list[tuple[str, str, int]] = []
        self.lock_contention = Event()

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def set(self, key: str, value: str, *, ex: int, nx: bool = False) -> bool:
        if nx and key in self.values:
            self.lock_contention.set()
            return False
        self.values[key] = value
        self.writes.append((key, value, ex))
        return True

    def eval(self, _script: str, _key_count: int, key: str, owner: str) -> int:
        if self.values.get(key) != owner:
            return 0
        del self.values[key]
        return 1


def test_problem_count_cache_loads_once_and_reuses_redis_value() -> None:
    redis = FakeRedis()
    cache = ProblemCatalogCountCache(redis)  # type: ignore[arg-type]
    loads: list[tuple[str | None, str | None]] = []

    def load_count(
        category: str | None, difficulty: str | None
    ) -> int:
        loads.append((category, difficulty))
        return 145

    assert cache.get_or_load(None, None, load_count) == 145
    assert cache.get_or_load(None, None, load_count) == 145

    assert loads == [(None, None)]
    assert redis.writes[-1][1:] == ("145", 24 * 60 * 60)


def test_problem_page_cache_reuses_page_for_same_cursor_and_filters() -> None:
    redis = FakeRedis()
    cache = ProblemCatalogCountCache(redis)  # type: ignore[arg-type]
    payload = {
        "items": [],
        "next_cursor": "next",
        "has_more": True,
        "total_count": 145,
    }

    loads = 0

    def load_page() -> dict[str, object]:
        nonlocal loads
        loads += 1
        return payload

    assert cache.get_page_or_load(None, None, 24, None, load_page) == payload
    assert cache.get_page_or_load(None, None, 24, None, load_page) == payload
    assert cache.get_page("Systems", None, 24, None) is None
    assert loads == 1
    assert redis.writes[-1][2] == 24 * 60 * 60


def test_problem_page_cache_prevents_a_stampede_on_a_cold_key() -> None:
    redis = FakeRedis()
    first_cache = ProblemCatalogCountCache(redis)  # type: ignore[arg-type]
    second_cache = ProblemCatalogCountCache(redis)  # type: ignore[arg-type]
    payload = {"items": [], "next_cursor": None, "has_more": False, "total_count": 145}
    loader_started = Event()
    release_loader = Event()
    loads = 0
    loads_lock = Lock()
    results: list[dict[str, object] | None] = []

    def load_page() -> dict[str, object]:
        nonlocal loads
        with loads_lock:
            loads += 1
        loader_started.set()
        assert release_loader.wait(timeout=2)
        return payload

    first_worker = Thread(
        target=lambda: results.append(
            first_cache.get_page_or_load(None, None, 24, None, load_page)
        )
    )
    first_worker.start()
    assert loader_started.wait(timeout=2)

    second_worker = Thread(
        target=lambda: results.append(
            second_cache.get_page_or_load(None, None, 24, None, load_page)
        )
    )
    second_worker.start()
    assert redis.lock_contention.wait(timeout=2)
    release_loader.set()

    first_worker.join(timeout=2)
    second_worker.join(timeout=2)

    assert not first_worker.is_alive()
    assert not second_worker.is_alive()
    assert loads == 1
    assert results == [payload, payload]
