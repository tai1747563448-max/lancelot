"""装配器的 Registry：扫描产出的 adapter 元数据表。

> 03-端口契约.md §"Registry 协议"
> Registry 不是端口，是端口层的全局表，记录所有已知 adapter 的元数据。
> V1 不扫 plugins/，所以 Registry V1 只装 adapter。

约束：
- `register` 时若 ID 已存在，抛 `DuplicateIdError`（继承 `RegistryError`；不静默覆盖）
- `find_*` 不存在的 ID/能力返回 None 或空列表，不抛异常
- V1 不实现删除——registry 在装配器启动时填充、退出时丢弃
- `find_by_capability` 只返回 manifest 中 `[capabilities].provides` 含该端口的 adapter
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from lancelot.domain.types import Adapter
from lancelot.errors import DuplicateIdError


class Registry:
    """全局注册表：把扫描得到的 `Adapter` 元数据按 ID / 端口两类索引。"""

    def __init__(self) -> None:
        # 双向索引：by_id 给 find_by_id 用；by_capability 给 selector 验证 requires 时用
        self._by_id: Dict[str, Adapter] = {}
        self._by_capability: Dict[str, List[str]] = {}

    # ---------- 写入 ----------

    def register(self, entry: Adapter) -> None:
        """注册一条 adapter。

        Args:
            entry: 已通过 manifest schema 校验的 `Adapter` dataclass。

        Raises:
            DuplicateIdError: 同 ID 已存在（不静默覆盖）。
        """
        if entry.id in self._by_id:
            raise DuplicateIdError(
                f"E_DUPLICATE_ID: adapter id '{entry.id}' already registered "
                f"(previous: {self._by_id[entry.id].name!r})"
            )
        self._by_id[entry.id] = entry
        for cap in entry.provides:
            self._by_capability.setdefault(cap.name, []).append(entry.id)

    # ---------- 读取 ----------

    def find_by_id(self, adapter_id: str) -> Optional[Adapter]:
        """按 ID 查找。找不到返回 None。"""
        return self._by_id.get(adapter_id)

    def find_by_capability(self, capability: str) -> List[Adapter]:
        """查找所有声明提供该端口的 adapter。

        注意：保留端口（`ModelPort` / `ChannelPort`）在 V1 永远返回空列表——
        因为没有 adapter 在 manifest 里声明它们（被 scan 阶段挡掉）。
        """
        ids = self._by_capability.get(capability, [])
        return [self._by_id[i] for i in ids]

    def all(self) -> List[Adapter]:
        """所有已注册 adapter 的列表。V1 不保证顺序。"""
        return list(self._by_id.values())

    def size(self) -> int:
        """已注册 adapter 数量。"""
        return len(self._by_id)

    # ---------- 调试辅助 ----------

    def __contains__(self, adapter_id: str) -> bool:
        return adapter_id in self._by_id

    def __iter__(self) -> Iterable[Adapter]:
        return iter(self._by_id.values())

    def __repr__(self) -> str:
        return f"Registry(size={self.size()}, ids={sorted(self._by_id)})"
