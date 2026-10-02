"""ChannelPort —— 输入输出契约（Lancelot 保留端口）。

> 03-端口契约.md §"ChannelPort"
>
> V1 实现位置：Lancelot 内部 `src/lancelot/channel_default/`。
> V1 不接受来自 `adapters/` 的实现——manifest 中
> `capabilities.provides = ["ChannelPort"]` 触发 `E_RESERVED_PORT` 警告。
"""
from __future__ import annotations

from typing import Optional, Protocol

from ..domain import Message


class ChannelPort(Protocol):
    """I/O 契约。负责从外界读、向外界写。"""

    def read(self) -> Optional[Message]:
        """读一条用户消息。EOF 时返回 None。"""

    def write(self, message: Message) -> None:
        """写一条消息（通常是 assistant 回复）。"""
