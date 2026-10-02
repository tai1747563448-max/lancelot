"""MemoryPort —— 记忆读写契约。

> 03-端口契约.md §"MemoryPort"
>
> V1 简化：
> - 没有语义检索 / embedding search / 过期策略 / 持久化——V2 起
> - 没有按 role 过滤 / 按时间过滤——V2 起
> - 失败抛 `MemoryError`

V1 仅接受 adapter 实现（adapters/memory/<name>/）。
"""
from __future__ import annotations

from typing import List, Optional, Protocol

from ..domain import MemoryEntry


class MemoryPort(Protocol):
    """记忆读写契约。"""

    def put(self, entry: MemoryEntry) -> None:
        """存一条记忆。key 重复时覆盖。"""

    def get(self, key: str) -> Optional[MemoryEntry]:
        """读一条记忆。key 不存在返回 None。"""

    def list(self, limit: int = 100) -> List[MemoryEntry]:
        """列出最近 limit 条记忆。V1 不保证顺序。"""

    def clear(self) -> None:
        """清空所有记忆。V1 不区分按用户清理 / 按类别清理。"""
