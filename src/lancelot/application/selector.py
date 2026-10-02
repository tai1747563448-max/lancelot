"""select 动作：根据用户指定从 Registry 中挑选 adapter，做必需/冲突检测。

> 04-装配器协议.md §"动作 2：select"
> V1 算法（伪代码见 04 §动作 2）：
>   1. 对每个 --use id：校验存在 / 未重复 / 不冲突 / 端口需求被满足
>   2. 一次扫描完成即可收敛（V1 requires 只指端口，不指 adapter id）

错误码（04 §动作 2 错误处理表）：
- E_ADAPTER_NOT_FOUND        → 退出码 3
- E_REQUIRE_NOT_MET          → 退出码 3
- E_CONFLICT                 → 退出码 3
- E_DUPLICATE_ID_IN_SELECTION → 退出码 3

注意：
- select **不**做完整传递闭包求解（V1 requires 只指端口）。V2 真依赖求解器。
- select **不**修改 Registry；只查询。
- select **不**写文件。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import List

from lancelot.application.registry import Registry
from lancelot.domain.types import Adapter
from lancelot.errors import (
    AdapterNotFoundError,
    ConflictError,
    DuplicateIdInSelectionError,
    RequireNotMetError,
)


# ---------- 配置 ----------


@dataclass(frozen=True)
class SelectResult:
    """select 的产物：选中的 adapter 列表（去重、按 --use 顺序）。"""

    selection: List[Adapter]


# ---------- 公开入口 ----------


def select(registry: Registry, ids: List[str]) -> SelectResult:
    """根据用户指定的 adapter ID 列表做选择。

    Args:
        registry: 已由 scan 填充的 Registry。
        ids: CLI `--use <id>` 列表（去重前的原始顺序）。

    Returns:
        SelectResult：合法选择结果。

    Raises:
        AdapterNotFoundError: ids 含有 registry 不存在的 ID。
        DuplicateIdInSelectionError: ids 中有重复。
        ConflictError: 选择结果包含 manifest.conflicts 中声明的互斥项。
        RequireNotMetError: 选择结果缺少 manifest.requires 中声明的端口提供方。
    """
    if not ids:
        # V1 默认行为：--use 不指定时，select Registry 里所有 adapter（便于调试）。
        # 04 §动作 2 输入允许这种用法。
        ids = [a.id for a in registry.all()]

    # 1. 重复 ID 检测
    seen: List[str] = []
    for aid in ids:
        if aid in seen:
            raise DuplicateIdInSelectionError(
                f"E_DUPLICATE_ID_IN_SELECTION: id '{aid}' appears multiple times"
            )
        seen.append(aid)

    # 2. 存在性检测 + 收集
    selected: List[Adapter] = []
    for aid in ids:
        adapter = registry.find_by_id(aid)
        if adapter is None:
            raise AdapterNotFoundError(
                f"E_ADAPTER_NOT_FOUND: id '{aid}' not present in registry "
                f"(known ids: {sorted(a.id for a in registry.all())})"
            )
        selected.append(adapter)

    # 3. 冲突检测（按 04 §V1 算法伪代码）
    selected_ids = {a.id for a in selected}
    for adapter in selected:
        for conflict_id in adapter.conflicts:
            if conflict_id in selected_ids:
                raise ConflictError(
                    f"E_CONFLICT: adapter '{adapter.id}' conflicts with '{conflict_id}'"
                )

    # 4. 必需端口检测
    provided_ports = {cap.name for a in selected for cap in a.provides}
    for adapter in selected:
        for req_cap in adapter.requires:
            if req_cap.name not in provided_ports:
                raise RequireNotMetError(
                    f"E_REQUIRE_NOT_MET: adapter '{adapter.id}' requires port "
                    f"'{req_cap.name}', but no selected adapter provides it"
                )

    return SelectResult(selection=selected)


# ---------- CLI 辅助 ----------


def print_selection(result: SelectResult, file=sys.stdout) -> None:
    """把选中列表一行行打到 file（默认 stdout）。"""
    ids = ", ".join(a.id for a in result.selection) or "<empty>"
    print(f"Selected: {ids}", file=file)
