"""launch 动作：fork-exec 启动已生成的 framework。

> 04-装配器协议.md §"动作 4：launch"
>
> launch **仅**是便利功能——用户完全可以不通过装配器启动生成物
> （`cd generated/<name> && python -m app.main`）。
> launch 不修改装配器状态、不修改生成物。

错误码（04 §动作 4 错误处理表）：
- E_GENERATED_DIR_MISSING → 退出码 5
- E_MAIN_PY_MISSING        → 退出码 5
- 子进程退出非零           → 透传子进程退出码
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from lancelot.errors import GenerateError


# ---------- 本地异常 ----------


class GeneratedDirMissingError(GenerateError):
    """E_GENERATED_DIR_MISSING：generated/<name>/ 不存在。"""


class MainPyMissingError(GenerateError):
    """E_MAIN_PY_MISSING：生成物目录下找不到 app/main.py。"""


# ---------- 公开入口 ----------


def launch(
    output_root: Path,
    name: str,
    *,
    python_executable: str | None = None,
) -> int:
    """用子进程启动 `generated/<name>/app/main.py`，返回子进程退出码。

    Args:
        output_root: 生成物根目录（默认 `./generated`）。
        name: 生成物子目录名。
        python_executable: 解释器路径，默认 `sys.executable`（当前 Python 解释器）。

    Returns:
        子进程退出码（透传）。0 表示正常退出。

    Raises:
        GeneratedDirMissingError: `output_root / name` 不存在。
        MainPyMissingError: `output_root / name / app / main.py` 不存在。
    """
    gen_dir = output_root / name
    if not gen_dir.is_dir():
        raise GeneratedDirMissingError(
            f"E_GENERATED_DIR_MISSING: '{gen_dir}' is not a directory"
        )

    main_py = gen_dir / "app" / "main.py"
    if not main_py.is_file():
        raise MainPyMissingError(
            f"E_MAIN_PY_MISSING: '{main_py}' not found; "
            f"did you forget to run `lancelot compose --name {name}`?"
        )

    if python_executable is None:
        python_executable = sys.executable

    # fork-exec：等价于 cd generated/<name> && python -m app.main
    # 透传 stdout/stderr，让子进程直接控制终端
    proc = subprocess.run(
        [python_executable, "-m", "app.main"],
        cwd=str(gen_dir),
        stdout=None,
        stderr=None,
    )
    return proc.returncode
