"""Lancelot 领域类型。

> 03-端口契约.md §"领域类型"
>
> 端口方法签名引用的所有类型。Lancelot 不引用任何外部 SDK 对象——模型供应商
> 的 message 格式（OpenAI 的、Anthropic 的）由 `ModelPort` 实现内部转换，
> **不得穿透到领域层**。

不变量（03 §不变量）：
- `Message` / `MemoryEntry` / `ToolCall` / `ToolResult` / `Task` /
  `Capability` / `Adapter` 都是 `@dataclass(frozen=True)`
- 只有 `Session` 是可变 dataclass（对话历史是 in-place 累积的）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional


# ---------- 对话消息 ----------


@dataclass(frozen=True)
class Message:
    """对话中的一条消息。

    Attributes:
        role: 消息角色（user / assistant / system / tool）。
        content: 文本内容。V1 不支持多模态。
        tool_call_id: 仅当 role==="tool" 时有意义，对应那个 ToolCall.id。
        tool_calls: 仅当 role==="assistant" 时有意义，模型请求调用的工具列表。
    """

    role: Literal["user", "assistant", "system", "tool"]
    content: str
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List["ToolCall"]] = None


# ---------- 会话 ----------


@dataclass
class Session:
    """一次会话。V1 不含状态机（STARTED / RUNNING / COMPLETED 等），V2 引入。

    Attributes:
        session_id: 全局唯一 ID。
        task_id: 关联到顶层 Task（可选）。
        messages: 有序消息列表（最后一条是最新）。
        metadata: 任意键值对（用户/系统标注）。
    """

    session_id: str
    task_id: Optional[str]
    messages: List[Message] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)


# ---------- 记忆条目 ----------


@dataclass(frozen=True)
class MemoryEntry:
    """记忆端口存储的最小条目。

    Attributes:
        key: 唯一标识。
        value: 文本内容。
        role: 可选，对应消息角色（V1 不强制）。
        timestamp: 可选，Unix 时间戳（V1 不强制）。

    不变量：key 在同一个 MemoryPort 实例内唯一（V1 不要求跨实例持久）。
    """

    key: str
    value: str
    role: Optional[Literal["user", "assistant", "system", "tool"]] = None
    timestamp: Optional[float] = None


# ---------- 工具调用 / 结果 ----------


@dataclass(frozen=True)
class ToolCall:
    """模型请求调用的一个工具。

    Attributes:
        id: 唯一 ID，与 ToolResult.tool_call_id 对应。
        name: 模块名，例如 "tools.echo"。
        arguments: JSON-like 参数。V1 不验证类型。
    """

    id: str
    name: str
    arguments: Dict[str, object]


@dataclass(frozen=True)
class ToolResult:
    """工具执行结果。

    Attributes:
        tool_call_id: 对应 ToolCall.id。
        content: 工具返回的文本结果。
        is_error: 工具是否报错。
    """

    tool_call_id: str
    content: str
    is_error: bool = False


# ---------- 任务 ----------


@dataclass(frozen=True)
class Task:
    """顶层任务（V1 仅作会话元数据，不参与调度；V2 引入任务队列与状态机）。"""

    task_id: str
    description: str
    metadata: Dict[str, str] = field(default_factory=dict)


# ---------- 能力 / adapter 自描述 ----------


@dataclass(frozen=True)
class Capability:
    """端口（port）的语义版本号。V1 简化：所有端口都是 1.0.0，版本号只是预留字段。"""

    name: str
    version: str


@dataclass(frozen=True)
class Adapter:
    """adapter 自描述元数据。由 scanner 从 MANIFEST.toml 解析后填充 Registry。

    Attributes:
        id: 例如 "memory.inmemory"。
        name: 人类可读。
        version: SemVer。
        category: V1 仅 "memory" / "tools"。
        description: 人类可读，<= 256 字符。
        min_framework: Lancelot 主版本约束。
        entry_module: Python 模块路径，从 adapters/ 根开始解析。
        entry_factory: 模块内的可调用名（无参工厂）。
        provides: 模块实现了哪些端口（V1 仅 [MemoryPort] 或 [ToolPort]）。
        requires: 模块依赖哪些端口。
        conflicts: 互斥的其它 adapter id。
        enhances: 协同的其它 adapter id（V1 仅作提示，不强制）。
        config_schema: 字段名 → 字段约束的映射。
    """

    id: str
    name: str
    version: str
    category: str
    description: str
    min_framework: str
    entry_module: str
    entry_factory: str
    provides: List[Capability]
    requires: List[Capability]
    conflicts: List[str]
    enhances: List[str]
    config_schema: Dict
