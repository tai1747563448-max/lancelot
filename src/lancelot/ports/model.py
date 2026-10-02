"""ModelPort —— 模型调用契约（Lancelot 保留端口）。

> 03-端口契约.md §"ModelPort"
>
> V1 实现位置：Lancelot 内部 `src/lancelot/model_default/`。
> V1 不接受来自 `adapters/` 的实现——manifest 中
> `capabilities.provides = ["ModelPort"]` 触发 `E_RESERVED_PORT` 警告。
"""
from __future__ import annotations

from typing import List, Protocol

from ..domain import Message


class ModelPort(Protocol):
    """模型调用契约。负责给定消息列表，返回模型回复。"""

    def generate(self, messages: List[Message]) -> Message:
        """同步生成。messages 是完整对话历史（不含模型即将生成的回复）。

        V1 不支持流式（streaming）——返回完整 Message。
        失败时抛 ModelError。

        实现可以接受额外 kwargs（V1 不强制签名严格——Protocol 是结构化的），
        例如 `mymodel.generate(messages, max_tokens=5)`。
        """
