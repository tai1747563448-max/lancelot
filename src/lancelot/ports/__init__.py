"""Lancelot ports 包——4 个 Protocol re-export。

使用：
    from lancelot.ports import MemoryPort, ToolPort, ModelPort, ChannelPort

注意：保留端口（ModelPort / ChannelPort）V1 仅 Lancelot 内部实现，
不允许 adapter 声明（被 scanner 警告 E_RESERVED_PORT）。
"""
from .channel import ChannelPort
from .memory import MemoryPort
from .model import ModelPort
from .tool import ToolPort

__all__ = [
    "ChannelPort",
    "MemoryPort",
    "ModelPort",
    "ToolPort",
]
