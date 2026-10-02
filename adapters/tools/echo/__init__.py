"""tools.echo —— 满足 ToolPort 的回显工具（V1 内置）。

duck-typed：本模块不直接 import Lancelot 领域类型，保证在 source tree
和 generated/<name>/adapters/tools/echo/ 下都能跑。

`invoke()` 返回 dict 而非 ToolResult 实例——loop._invoke_tool 的
duck-typing 适配层（三种形态：ToolResult / dict / duck-typed）会把
dict 包装成 ToolResult(tool_call_id=call.id, ...)。
"""
from __future__ import annotations

import json
from typing import Any, Dict


def create_tool() -> "EchoTool":
    """无参工厂（按 02 §entry.factory 调用约定）。"""
    return EchoTool()


class EchoTool:
    """回显工具：把 kwargs 序列化为 JSON 字符串返回。"""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return (
            "Echo back the arguments as a JSON string. "
            "The simplest tool implementation, used to demonstrate ToolPort."
        )

    @property
    def parameters_schema(self) -> Dict:
        """JSON Schema。V1 仅参考——不强制校验。"""
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Free-form text to echo back",
                },
            },
            "required": [],
            "additionalProperties": True,
        }

    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        """执行回显。

        返回 dict 形态：`{"content": <str>, "is_error": <bool>}`。
        loop 会包成真正的 ToolResult 并填上 tool_call_id。
        """
        return {
            "content": json.dumps(kwargs, ensure_ascii=False, sort_keys=True),
            "is_error": False,
        }
