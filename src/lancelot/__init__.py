"""Lancelot 元框架——造 agent 框架的工具。

> V1 是 Lancelot 元框架的**最小可用版本**（详见 `docs/01-V1范围与边界.md`）。
>
> 本包是装配器本身（`lancelot` 命令的实现），不包含任何 adapter 业务代码。
> adapter 在仓库根的 `adapters/` 子目录下。

用法：
    python -m lancelot scan
    python -m lancelot run
    python -m lancelot compose --use memory.inmemory --use tools.echo --name myapp
    python -m lancelot launch myapp

依赖方向（hexagonal，自底向上）：
    errors.py + domain/ + ports/ + loop/ + model_default/ + channel_default/
        ↓
    application/  ← 装配器业务（scan / select / generate / launch / run）
        ↓
    cli.py + __main__.py  ← 你在这里
"""
from __future__ import annotations

from lancelot.application import AssemblerState
from lancelot.errors import LancelotError

__version__ = "1.0.0"

__all__ = [
    "AssemblerState",
    "LancelotError",
    "__version__",
]
