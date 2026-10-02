"""Lancelot ports 包——4 个 Protocol re-export。

使用：
    from lancelot.ports import MemoryPort, ToolPort, ModelPort, ChannelPort

注意：保留端口（ModelPort / ChannelPort）V1 仅 Lancelot 内部实现，
不允许 adapter 声明（被 scanner 警告 E_RESERVED_PORT）。
"""
from lancelot.ports.channel import ChannelPort
from lancelot.ports.memory import MemoryPort
from lancelot.ports.model import ModelPort
from lancelot.ports.tool import ToolPort

__all__ = [
    "ChannelPort",
    "MemoryPort",
    "ModelPort",
    "ToolPort",
]
