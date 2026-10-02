"""装配器内部状态。

> 04-装配器协议.md §"内部状态（v1）"
> 状态仅在装配器进程内存里，不持久化。重启必须重跑 scan。

四个动作（scan / select / generate / launch，以及 v1.2 新增的 run）共享同一份
`AssemblerState`。它的字段是"装配器一次调用能用到的全部上下文"。

设计要点：
- 用字符串注解 `"Registry"` 避免 state ↔ registry 循环 import
- `registry` 默认 None，由 cli.py 在装配器启动时注入一个 `Registry()` 实例
- `selection` 默认空列表，由 select 动作填充
- `name` 默认 None，由 generate 动作写入
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from lancelot.domain.types import Adapter

if TYPE_CHECKING:
    from lancelot.application.registry import Registry


@dataclass
class AssemblerState:
    """装配器进程级状态。

    Attributes:
        adapters_root: adapter 源根目录（默认 `./adapters`）。
        plugins_root: plugin 源根目录（默认 `./plugins`，V1 留空不读）。
        output_root: 生成物输出根目录（默认 `./generated`）。
        registry: 由 scan 填充。装配器启动时由 cli.py 注入一个 Registry 实例。
        selection: 由 select 填充；select 之前是空列表。
        name: generate 的目标子目录名（如 `myapp`），generate 之前为 None。
    """

    adapters_root: Path = field(default_factory=lambda: Path("./adapters"))
    plugins_root: Path = field(default_factory=lambda: Path("./plugins"))
    output_root: Path = field(default_factory=lambda: Path("./generated"))

    registry: Optional["Registry"] = None
    selection: List[Adapter] = field(default_factory=list)
    name: Optional[str] = None
