"""`python -m lancelot` 入口。

启动方式之一：
    python -m lancelot scan
    python -m lancelot run
    python -m lancelot compose --use memory.inmemory --name myapp
    python -m lancelot launch myapp

另一个启动方式（仓库根）：`python -m lancelot.cli` 或 `python -c
"from lancelot.cli import main; sys.exit(main())"`。
"""
from __future__ import annotations

import sys

from lancelot.cli import main

if __name__ == "__main__":
    sys.exit(main())
