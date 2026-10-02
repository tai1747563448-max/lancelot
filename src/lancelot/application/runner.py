"""run 动作（v1.2 新增）：bare Lancelot 直接跑，不生成任何文件。

> 04-装配器协议.md §"动作 5：run"
>
> **bare Lancelot 直接跑**——不接任何 adapter，直接调用 Lancelot 的内部 default 组合：
> - loop = single_loop.create_loop()
> - model = model_default.mock.create_model()
> - channel = channel_default.stdio.create_channel()
> - loop.run(session)
>
> `run` 是 V1 成功判据 2 的支撑命令——证明 bare Lancelot 自洽
> `run` 与 `compose --use nothing` 的区别：`run` 不生成文件，`compose` 必须生成文件
> `run` 不接受 `--use`，因为没有 adapter 可选

关键纪律：
- `run` 不写任何文件
- `run` 不接任何 adapter
- `run` 是便利入口；用户完全可以写一段 Python 直接 `create_loop(...).run(...)`
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from lancelot.domain import Session
from lancelot.errors import LancelotError
from lancelot.loop.single_loop import create_loop
from lancelot.model_default.mock import create_model
from lancelot.channel_default.stdio import create_channel


# ---------- 公开入口 ----------


def run(
    *,
    config_path: Optional[Path] = None,
    max_turns: int = 10,
) -> int:
    """以 bare Lancelot 形态跑一次对话循环。

    Args:
        config_path: Lancelot 内部默认实现的配置文件路径（V1 mock 可选）。
        max_turns: 单次循环最大步数（防止无限循环）。

    Returns:
        进程退出码（0 = 正常；非 0 = 错误；130 = Ctrl+C）。

    Raises:
        LancelotError: 内部组件初始化失败 / 运行失败。
    """
    # 1. 实例化 Lancelot 内部 default 三件套
    #    注意：这里是 Lancelot 的 `src.lancelot.`（不是生成物的 `lancelot_runtime.`）
    #    装配器本身就跑在 Lancelot 源码树里。
    model = create_model()
    channel = create_channel()
    loop = create_loop(
        model=model,
        channel=channel,
        memory=None,
        tools=[],
        max_turns=max_turns,
    )

    # 2. 准备 session
    session = Session(
        session_id="bare",
        task_id=None,
        messages=[],
        metadata={"bare": True},
    )

    # 3. 启动循环（Ctrl+C 由 main 透传 130）
    try:
        loop.run(session)
    except KeyboardInterrupt:
        return 130
    return 0
