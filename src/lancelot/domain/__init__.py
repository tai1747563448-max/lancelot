"""Lancelot domain 包——领域类型 re-export。

使用：
    from lancelot.domain import Message, Session, Adapter
"""
from .types import (
    Adapter,
    Capability,
    MemoryEntry,
    Message,
    Session,
    Task,
    ToolCall,
    ToolResult,
)

__all__ = [
    "Adapter",
    "Capability",
    "MemoryEntry",
    "Message",
    "Session",
    "Task",
    "ToolCall",
    "ToolResult",
]
