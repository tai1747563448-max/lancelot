"""memory.lru —— 满足 MemoryPort 的 LRU 实现（V1 第二个内置 mock）。

duck-typed：本模块不直接 import Lancelot 领域类型，保证：
- 在 source tree（adapters/）下可被 scan 阶段跳过（scan 不执行代码）
- 被 generator 复制到 generated/<name>/adapters/memory/lru/ 后
  无需任何 import 修正即可被生成物 import

与 memory.inmemory 的差异：
- 淘汰策略：LRU（最近最少使用）而非 FIFO
- 默认容量：512 而非 1024
- get() 也会刷新"最近使用"位置（OrderedDict.move_to_end）
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, List, Optional


def create_memory() -> "LruMemory":
    """无参工厂（按 02 §entry.factory 调用约定）。

    V1 不支持带参数的 factory。配置通过 instance.configure(dict) 注入。
    """
    return LruMemory()


class LruMemory:
    """满足 MemoryPort（duck-typed）。LRU 淘汰。"""

    def __init__(self) -> None:
        # OrderedDict[str, MemoryEntry-like]；插入/访问顺序由 OrderedDict 维护
        self._store: "OrderedDict[str, Any]" = OrderedDict()
        self._max_entries: int = 512  # default；configure 覆盖（与 inmemory 的 1024 区分）

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
        """存一条记忆。key 重复时覆盖并标记为最近使用。超过 max_entries 时 LRU 淘汰。

        LRU 语义：
        - 新 key → 插入到 OrderedDict 末尾（最近使用）
        - 已存在 key → 更新 value 并 move_to_end 标记为最近使用
        - 超过 max_entries → popitem(last=False) 淘汰最旧插入/最久未访问者
        """
        key = entry.key
        if key in self._store:
            # 覆盖：删除旧条目后重新插入，使其移到末尾
            del self._store[key]
        self._store[key] = entry
        while len(self._store) > self._max_entries:
            # last=False 弹出 OrderedDict 头部（最久未使用）
            self._store.popitem(last=False)

    def get(self, key: str) -> Optional[Any]:
        """读一条记忆。同时把它标记为"最近使用"（move_to_end）。

        key 不存在返回 None，且不动 OrderedDict 顺序。
        """
        if key not in self._store:
            return None
        value = self._store[key]
        # 刷新访问顺序：移到末尾即为"最近使用"
        self._store.move_to_end(key)
        return value

    def list(self, limit: int = 100) -> List[Any]:
        """列出最近 limit 条记忆。V1 不保证顺序。"""
        return list(self._store.values())[:limit]

    def clear(self) -> None:
        """清空所有记忆。"""
        self._store.clear()
