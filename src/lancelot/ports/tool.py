"""ToolPort —— 工具契约。

> 03-端口契约.md §"ToolPort"
>
> V1 仅接受 adapter 实现（adapters/tools/<name>/）。
"""
from __future__ import annotations

from typing import Dict, Protocol

from ..domain import ToolResult


class ToolPort(Protocol):
    """工具契约。负责被 agent 调用、执行一个动作、返回结果。"""

    @property
    def name(self) -> str:
        """工具名（给 LLM 看），例如 'echo'。"""

    @property
    def description(self) -> str:
        """工具描述（给 LLM 看）。V1 不限制长度。"""

    @property
    def parameters_schema(self) -> Dict:
        """工具参数的 JSON Schema。V1 仅做参考——不强制校验。"""

    def invoke(self, **kwargs: object) -> ToolResult:
        """执行工具。kwargs 由 LLM 生成（来自 ToolCall.arguments）。

        失败抛 ToolError（被 is_error=False 包裹后返回也允许）。
        """
