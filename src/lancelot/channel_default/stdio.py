"""V1 唯一默认 channel 实现（stdin/stdout）。

> 03-端口契约.md §"ChannelPort V1 实现位置"
>
> V1 是 stdio；V2 起加 HTTP / WebSocket。
> Lancelot 保留端口，V1 不接受来自 adapters/ 的实现。
"""
from __future__ import annotations

import sys
from typing import Optional, TextIO

from ..domain import Message
from ..errors import ChannelError


def create_channel(
    *,
    prompt: str = "> ",
    output: Optional[TextIO] = None,
    input_stream: Optional[TextIO] = None,
) -> "StdioChannel":
    """工厂：实例化 V1 默认 stdio channel。生成物里 composition.py 调这个。

    Args:
        prompt: 每次 read 前打印的提示符。
        output: 写出目标（默认 `sys.stdout`）。
        input_stream: 读入源（默认 `sys.stdin`）。测试时可注入 `io.StringIO`。
    """
    return StdioChannel(
        prompt=prompt,
        output=output,
        input_stream=input_stream,
    )


class StdioChannel:
    """V1 stdio channel：从 stdin 读 user 消息、stdout 写 assistant 回复。"""

    def __init__(
        self,
        *,
        prompt: str = "> ",
        output: Optional[TextIO] = None,
        input_stream: Optional[TextIO] = None,
    ) -> None:
        self._prompt = prompt
        self._output = output if output is not None else sys.stdout
        self._input = input_stream if input_stream is not None else sys.stdin

    def read(self) -> Optional[Message]:
        """读一行用户输入。EOF 时返回 None（按 ChannelPort 协议）。

        KeyboardInterrupt 不在这里捕获——让它透传到 caller（loop / main），
        由 `runner.run` 转 130 退出码。
        """
        try:
            self._output.write(self._prompt)
            self._output.flush()
            line = self._input.readline()
        except EOFError:
            return None
        except OSError as e:
            raise ChannelError(f"stdio channel: read failed: {e}") from e

        if not line:  # 空字符串 = EOF（Ctrl+D / 文件尾）
            return None
        return Message(role="user", content=line.rstrip("\n").rstrip("\r"))

    def write(self, message: Message) -> None:
        """把消息写到 stdout。"""
        try:
            self._output.write(message.content + "\n")
            self._output.flush()
        except OSError as e:
            raise ChannelError(f"stdio channel: write failed: {e}") from e
