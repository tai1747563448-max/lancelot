"""Lancelot 装配器——V1 元框架的核心业务层。

V1 暴露 5 个动作（按 04-装配器协议.md）：

- scan —— scanner.scan()
- select —— selector.select()
- generate —— generator.generate()
- launch —— launcher.launch()
- run —— runner.run()（v1.2 新增；bare 模式）

模块依赖方向（hexagonal）：
    cli.py / __main__.py
         ↓
    application/  ← 你在这里
         ↓
    ports/ + loop/ + model_default/ + channel_default/
         ↓
    domain/ + errors.py
"""
from lancelot.application.state import AssemblerState

__all__ = ["AssemblerState"]
