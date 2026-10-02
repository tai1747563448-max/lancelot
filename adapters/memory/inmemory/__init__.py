"""memory.inmemory —— 满足 MemoryPort 的内存实现（V1 内置）。

duck-typed：本模块不直接 import Lancelot 领域类型，保证：
- 在 source tree（adapters/）下可被 scan 阶段跳过（scan 不执行代码）
- 被 generator 复制到 generated/<name>/adapters/memory/inmemory/ 后
  无需任何 import 修正即可被生成物 import

生成物的 composition.py 会调 `create_memory()` 拿实例，再
`instance.configure({"max_entries": 1024})` 套用 manifest defaults。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def create_memory() -> "InMemoryMemory":
    """无参工厂（按 02 §entry.factory 调用约定）。

    V1 不支持带参数的 factory。配置通过 instance.configure(dict) 注入。
    """
    return InMemoryMemory()


class InMemoryMemory:
    """满足 MemoryPort（duck-typed）。"""

    def __init__(self) -> None:
        # Dict[str, MemoryEntry-like]；key 为 MemoryEntry.key
        self._store: Dict[str, Any] = {}
        self._max_entries: int = 1024  # default；configure 覆盖

    # ---------- composition.py 注入入口 ----------

    def configure(self, cfg: Dict[str, Any]) -> None:
        """套用 manifest config_schema 的 defaults。生成物里在 create_memory() 后调用。

        V1 简化：V1 装配器在 compose 时仅透传 manifest `[config].schema.default`
        给 configure()。required=true 且 default 未给的字段由 generator 写
        一行注释到 config.yaml。
        """
        if "max_entries" in cfg:
            self._max_entries = int(cfg["max_entries"])

    # ---------- MemoryPort ----------

    def put(self, entry: Any) -> None:
        """存一条记忆。key 重复时覆盖。超过 max_entries 时 FIFO 截断。"""
        self._store[entry.key] = entry
        while len(self._store) > self._max_entries:
            # V1 §MemoryPort.list() 不保证顺序 → 简单 pop first
            self._store.pop(next(iter(self._store)))

    def get(self, key: str) -> Optional[Any]:
        """读一条记忆。key 不存在返回 None。"""
        return self._store.get(key)

    def list(self, limit: int = 100) -> List[Any]:
        """列出最近 limit 条记忆。V1 不保证顺序。"""
        return list(self._store.values())[:limit]

    def clear(self) -> None:
        """清空所有记忆。"""
        self._store.clear()
