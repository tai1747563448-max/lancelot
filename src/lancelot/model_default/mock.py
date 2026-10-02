"""V1 唯一默认 model 实现（mock）。

> 03-端口契约.md §"ModelPort V1 实现位置"
>
> V1 是 mock；V1.1 起此处加 openai.py / anthropic.py 等。
> Lancelot 保留端口，V1 不接受来自 adapters/ 的实现。
"""
from __future__ import annotations

from typing import List

from lancelot.domain import Message
from lancelot.errors import ModelError


def create_model() -> "MockModel":
    """工厂：实例化 V1 默认 mock model。生成物里 composition.py 调这个。"""
    return MockModel()


class MockModel:
    """V1 mock model：把最后一条消息的 content 前缀 `[mock]` 回写。

    设计意图：跑通 happy path + 暴露 ToolCall 协议形状（不实际调工具——
    V1 mock 不返回 tool_calls，要真调工具得用真 model）。
    """

    PREFIX = "[mock] "

    def generate(self, messages: List[Message]) -> Message:
        """同步生成。V1 简化：取最后一条消息做 echo。"""
        if not messages:
            raise ModelError("mock model: cannot generate from empty message list")
        last = messages[-1]
        return Message(
            role="assistant",
            content=f"{self.PREFIX}{last.content}",
        )
