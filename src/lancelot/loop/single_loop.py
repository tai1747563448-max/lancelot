"""Lancelot 唯一 agent loop（V1）。

> 03-端口契约.md §"端口之间的关系"
>
>     ChannelPort → user message → loop → ModelPort → assistant
>                                       ↓
>                                       ToolPort ↘
>                                       MemoryPort
>
> loop 不是端口（V1 不定义 `AgentLoopPort`），是 Lancelot 内部的协调者。
> V1 没有第二个 loop 可选。

V1 算法（V1 mock model 不返回 tool_calls，但仍保留工具调用处理路径以兼容未来真 model）：

    for each turn (≤ max_turns outer):
        user_msg = channel.read()
        if user_msg is None: return               # EOF
        session.messages.append(user_msg)
        for each turn (≤ max_turns inner):
            assistant = model.generate(messages)
            if assistant.tool_calls:               # 真 model 才走这条路
                for call in tool_calls:
                    result = invoke tool（包 is_error=True/False）
                    messages.append(Message(role="tool", ...))
                continue                          # 让模型看 tool 结果再回答
            session.messages.append(assistant)
            break
        channel.write(assistant)
        memory.put(MemoryEntry(...)) if memory
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..domain import MemoryEntry, Message, Session, ToolResult
from ..errors import LoopError, ModelError
from ..ports import ChannelPort, MemoryPort, ModelPort, ToolPort


def create_loop(
    *,
    model: ModelPort,
    channel: ChannelPort,
    memory: Optional[MemoryPort],
    tools: List[ToolPort],
    max_turns: int = 10,
) -> "SingleLoop":
    """工厂：组装 loop 实例。生成物里 composition.py 调这个。"""
    if max_turns <= 0:
        raise LoopError(f"create_loop: max_turns must be > 0, got {max_turns}")
    return SingleLoop(
        model=model,
        channel=channel,
        memory=memory,
        tools=tools,
        max_turns=max_turns,
    )


class SingleLoop:
    """V1 唯一 loop。Ctrl+C 由 caller 处理（runner.run 透传 KeyboardInterrupt → 130）。"""

    def __init__(
        self,
        *,
        model: ModelPort,
        channel: ChannelPort,
        memory: Optional[MemoryPort],
        tools: List[ToolPort],
        max_turns: int,
    ) -> None:
        self._model = model
        self._channel = channel
        self._memory = memory
        # 用 dict 索引：tool invoke 时按 name 找
        self._tools: Dict[str, ToolPort] = {t.name: t for t in tools}
        self._max_turns = max_turns

    def run(self, session: Session) -> None:
        """主循环：Channel → Model → Tool → Memory → Channel，直到 EOF 或超 max_turns。"""
        for _ in range(self._max_turns):
            user_msg = self._channel.read()
            if user_msg is None:
                return  # EOF：连接断了就别再问
            session.messages.append(user_msg)

            assistant = self._run_inner_loop(session)

            session.messages.append(assistant)
            self._channel.write(assistant)

            # 记入 memory（仅当 adapter 提供 memory 时）
            if self._memory is not None and user_msg.role == "user":
                try:
                    self._memory.put(
                        MemoryEntry(
                            key=f"msg-{len(session.messages)}",
                            value=user_msg.content,
                            role=user_msg.role,
                        )
                    )
                except Exception as e:
                    # Memory 错误不应让 loop 崩——记一行 stderr 后继续
                    import sys
                    print(f"[loop] memory.put failed: {e}", file=sys.stderr)

        # 外层循环耗尽：max_turns 用完
        raise LoopError(
            f"single_loop: max_turns={self._max_turns} exhausted without EOF"
        )

    # ---------- 内部 ----------

    def _run_inner_loop(self, session: Session) -> Message:
        """处理可能的 tool 调用链：让模型反复思考，直到给出最终 assistant 回复。

        V1 mock 不会返回 tool_calls，所以内层一次 break；真 model 可能多次迭代。
        """
        for _ in range(self._max_turns):
            try:
                assistant = self._model.generate(session.messages)
            except ModelError:
                raise  # 让 caller 看见

            if not assistant.tool_calls:
                return assistant  # 最终回复

            # 有 tool_calls：执行工具，把结果写回 session，继续让模型思考
            for call in assistant.tool_calls:
                result = self._invoke_tool(call)
                session.messages.append(
                    Message(
                        role="tool",
                        content=result.content,
                        tool_call_id=result.tool_call_id,
                    )
                )

        raise LoopError(
            f"single_loop: inner tool loop exhausted (max_turns={self._max_turns})"
        )

    def _invoke_tool(self, call: Any) -> ToolResult:
        """调用一个工具。tool 不存在或抛错时返回 is_error=True（不破坏 loop）。

        adapter 可以返回三种 duck-typed 形态：
        1. `ToolResult` 实例：尊重 content / is_error，只覆盖 tool_call_id
        2. `dict`：`{"content": ..., "is_error": bool}`
        3. 任何其它对象：str() 化、is_error=False
        这样 adapter 无需 import Lancelot 的 ToolResult dataclass——
        它只 import duck-typed 接口，可以同时在 source tree 和
        generated/<name>/adapters/<id>/ 下跑。
        """
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(
                tool_call_id=call.id,
                content=f"tool '{call.name}' not registered",
                is_error=True,
            )
        try:
            raw = tool.invoke(**call.arguments)
        except Exception as e:
            return ToolResult(
                tool_call_id=call.id,
                content=f"tool '{call.name}' raised: {e}",
                is_error=True,
            )

        # duck-typing 适配
        if isinstance(raw, ToolResult):
            return ToolResult(
                tool_call_id=call.id,
                content=raw.content,
                is_error=raw.is_error,
            )
        if isinstance(raw, dict):
            return ToolResult(
                tool_call_id=call.id,
                content=str(raw.get("content", raw)),
                is_error=bool(raw.get("is_error", False)),
            )
        if hasattr(raw, "content") and hasattr(raw, "is_error"):
            return ToolResult(
                tool_call_id=call.id,
                content=str(raw.content),
                is_error=bool(raw.is_error),
            )
        return ToolResult(
            tool_call_id=call.id,
            content=str(raw),
            is_error=False,
        )
