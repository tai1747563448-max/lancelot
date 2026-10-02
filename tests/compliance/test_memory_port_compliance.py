"""MemoryPort 契约一致性（compliance）测试。

V1 第 6 条成功判据：MemoryPort 协议由任何实现该协议的 adapter 都满足。

测试设计：
- **不** import `lancelot.domain.MemoryEntry` —— 使用 `types.SimpleNamespace`
  构造只带 `.key` / `.value`（外加可选 `.role` / `.timestamp`）的简易对象。
  理由：adapters/memory/inmemory/__init__.py 是 duck-typed 的（不依赖
  lancelot 领域类型），compliance 测试应当验证"任何长得像 MemoryEntry 的
  对象都能 work"，而不是验证"只有 Lancelot 自己的 dataclass 才能 work"。
- 参数化 over 两套 adapter 实现（FIFO InMemory / LRU），由 `_try_import`
  实现 LRU adapter 还没就绪时的 graceful skip。

如何运行（必须在 Lancelot 仓库根目录）：
    PYTHONPATH=src pytest tests/compliance/test_memory_port_compliance.py -v
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, List, Optional

import pytest


# ---------- 鸭子类型 entry 工厂 ----------


def _entry(key: str, value: str, role: Optional[str] = None, timestamp: Optional[float] = None) -> Any:
    """构造一个长得像 MemoryEntry 的简单对象。

    SimpleNamespace 故意只用属性访问（adapter 只读 .key / .value），
    不实现 __eq__ / __hash__ 之外的 MagicMethod。这样能最严格地检验
    adapter 是否真的只依赖协议规定的属性访问。
    """
    return SimpleNamespace(key=key, value=value, role=role, timestamp=timestamp)


def _entries_equal(a: Any, b: Any) -> bool:
    """字段级相等比较，避免 SimpleNamespace 默认按 identity 比较。"""
    if a is None or b is None:
        return a is b
    return (
        a.key == b.key
        and a.value == b.value
        and getattr(a, "role", None) == getattr(b, "role", None)
        and getattr(a, "timestamp", None) == getattr(b, "timestamp", None)
    )


# ---------- adapter 发现（robust import） ----------


def _try_import(module_name: str, factory_name: str) -> Optional[Callable[[], Any]]:
    """按 "adapters.memory.<name>" 路径导入；失败返回 None（不抛）。"""
    try:
        mod = __import__(module_name, fromlist=[factory_name])
        return getattr(mod, factory_name)
    except ImportError:
        return None


# 必须存在的 adapter
_create_inmemory = _try_import("adapters.memory.inmemory", "create_memory")
assert _create_inmemory is not None, (
    "FATAL: adapters.memory.inmemory 必须存在（V1 内置 adapter）；"
    "找不到时整个 compliance 测试套件无意义。"
)


# 可选 adapter（由并行 agent 落盘，可能尚未就绪）
_create_lru = _try_import("adapters.memory.lru", "create_memory")


# pytest 参数化表：(factory, default_max_entries)
_ADAPTER_PARAMS = [
    pytest.param(_create_inmemory, 1024, id="inmemory"),
]
if _create_lru is not None:
    _ADAPTER_PARAMS.append(pytest.param(_create_lru, 512, id="lru"))


# ---------- 测试类 ----------


@pytest.mark.parametrize("create_memory, default_max_entries", _ADAPTER_PARAMS)
class TestMemoryPortContract:
    """任何实现 MemoryPort 的 adapter 都必须满足这些不变量。

    每个测试都通过 `_ADAPTER_PARAMS` 参数化，对所有已注册的 adapter 执行。
    """

    # ---- put + get ----

    def test_put_then_get_returns_equal_entry(self, create_memory: Callable[[], Any], default_max_entries: int) -> None:
        """put 一条 → get 同 key → 返回的 entry 与原 entry 字段相等。"""
        mem = create_memory()
        original = _entry("k1", "hello", role="user", timestamp=1.0)

        mem.put(original)
        got = mem.get("k1")

        assert got is not None, "put 后 get 必须返回非 None"
        assert _entries_equal(got, original), (
            f"put 后 get 返回的 entry 与原 entry 字段不一致: "
            f"got={got!r} vs original={original!r}"
        )

    def test_put_with_duplicate_key_overwrites(self, create_memory: Callable[[], Any], default_max_entries: int) -> None:
        """put 同 key 两次 → value 是后写入的；size 不增（仍为 1）。"""
        mem = create_memory()
        mem.put(_entry("k", "v1"))
        mem.put(_entry("k", "v2"))

        got = mem.get("k")
        assert got is not None
        assert got.value == "v2", "duplicate key 必须被新值覆盖"
        # 容量为 default_max_entries；size ≤ capacity
        assert len(mem.list(limit=default_max_entries * 10)) == 1, (
            "duplicate key 不应增加条目数；当前 list 返回了多条"
        )

    def test_get_missing_key_returns_none(self, create_memory: Callable[[], Any], default_max_entries: int) -> None:
        """get 一个从未 put 过的 key 必须返回 None。"""
        mem = create_memory()
        assert mem.get("never-inserted") is None

        # 即使存了别的 key，缺失 key 仍返回 None
        mem.put(_entry("exists", "yes"))
        assert mem.get("does-not-exist") is None

    # ---- list ----

    def test_list_respects_limit(self, create_memory: Callable[[], Any], default_max_entries: int) -> None:
        """list(limit) 最多返回 limit 条（≤ 100 时不触发截断）。"""
        mem = create_memory()
        n = min(default_max_entries, 50)  # 默认 limit=100；只放 50 条不会截断
        for i in range(n):
            mem.put(_entry(f"k{i}", f"v{i}"))

        result = mem.list(limit=100)
        assert isinstance(result, list), "list() 必须返回 list"
        assert len(result) <= 100, f"list(limit=100) 不应超过 100 条；got {len(result)}"
        assert len(result) == n, f"放 {n} 条，list 应返回 {n} 条；got {len(result)}"

        # 同时验证 limit=10 真的截到 10
        capped = mem.list(limit=10)
        assert len(capped) == 10, f"list(limit=10) 应返回 10 条；got {len(capped)}"

    def test_list_returns_empty_after_clear(self, create_memory: Callable[[], Any], default_max_entries: int) -> None:
        """clear 后 list() 必须为空 list（不是 None、不是非空）。"""
        mem = create_memory()
        mem.put(_entry("a", "1"))
        mem.put(_entry("b", "2"))
        mem.clear()

        result = mem.list()
        assert result == [], f"clear 后 list() 必须返回 []；got {result!r}"

    # ---- clear ----

    def test_clear_removes_all_keys(self, create_memory: Callable[[], Any], default_max_entries: int) -> None:
        """clear 后所有之前 put 的 key get 都返回 None。"""
        mem = create_memory()
        keys = [f"k{i}" for i in range(20)]
        for k in keys:
            mem.put(_entry(k, f"v-{k}"))

        # clear 前能取到
        assert mem.get(keys[0]) is not None

        mem.clear()

        for k in keys:
            assert mem.get(k) is None, f"clear 后 get({k!r}) 必须返回 None"

    # ---- eviction policy（adapter-specific，仅断言不变量）----

    def test_size_never_exceeds_max_entries(self, create_memory: Callable[[], Any], default_max_entries: int) -> None:
        """放入超过 max_entries 数量的条目后，size ≤ max_entries。

        不断言哪一条被淘汰——FIFO / LRU 行为不同，参见各自的 adapter 测试。
        """
        mem = create_memory()
        overshoot = default_max_entries + 50
        for i in range(overshoot):
            mem.put(_entry(f"k{i}", f"v{i}"))

        # 默认 limit=100 可能不足以窥全貌；用足够大的 limit 看真实 size
        actual_size = len(mem.list(limit=10_000))
        assert actual_size <= default_max_entries, (
            f"put {overshoot} 条进入 capacity={default_max_entries} 的 store，"
            f"size 应 ≤ {default_max_entries}；got {actual_size}"
        )

    def test_most_recent_put_is_retrievable(self, create_memory: Callable[[], Any], default_max_entries: int) -> None:
        """最后 put 的 entry 一定能 get 到（直到被淘汰为止）。

        把 capacity 设得足够大，确保最后一条不会立刻被淘汰。
        """
        mem = create_memory()
        mem.configure({"max_entries": default_max_entries + 100})  # 给足空间

        last = _entry("last-key", "last-value")
        mem.put(last)

        got = mem.get("last-key")
        assert got is not None, "最后一次 put 的 entry 必须能被 get"
        assert got.value == "last-value"

    # ---- configure ----

    def test_configure_reduces_max_entries(self, create_memory: Callable[[], Any], default_max_entries: int) -> None:
        """configure({"max_entries": N}) 后，put N+1 条 → size ≤ N。

        从默认 capacity 缩小到一个较小的 N（< default_max_entries），便于断言。
        """
        mem = create_memory()
        new_cap = max(2, default_max_entries // 4)  # 保证 new_cap 至少为 2
        mem.configure({"max_entries": new_cap})

        for i in range(new_cap + 1):
            mem.put(_entry(f"k{i}", f"v{i}"))

        actual_size = len(mem.list(limit=10_000))
        assert actual_size <= new_cap, (
            f"configure(max_entries={new_cap}) 后 put {new_cap + 1} 条，"
            f"size 应 ≤ {new_cap}；got {actual_size}"
        )
