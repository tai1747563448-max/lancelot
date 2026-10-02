"""generate 动作：把选中 adapter 烘进 generated/<name>/。

> 04-装配器协议.md §"动作 3：generate"
> 07-生成物结构.md

关键纪律（V1 不变量）：
- **复制而非引用** Lancelot runtime：拷贝 `src/lancelot/` 子集到 `generated/<name>/lancelot_runtime/`
- **adapter 也复制而非引用**：拷贝 `adapters/<id>/` 到 `generated/<name>/adapters/<id>/`
- 生成物不持有 Lancelot source tree 的引用——生成物的 import 必须用 `lancelot_runtime.` 前缀
- 生成物不持有装配器的引用——生成物不调用 `lancelot.compose` / `lancelot.scan`

错误码（04 §动作 3 错误处理表）：
- E_OUTPUT_DIR_EXISTS         → 退出码 4（除非 --force）
- E_COPY_FAILED               → 退出码 4
- E_TEMPLATE_RENDER_FAILED    → 退出码 4
"""
from __future__ import annotations

import datetime as _dt
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from lancelot.application.state import AssemblerState
from lancelot.domain.types import Adapter
from lancelot.errors import (
    CopyFailedError,
    OutputDirExistsError,
    TemplateRenderFailedError,
)


# ---------- 报告 ----------


@dataclass
class GenerateReport:
    """generate 的产物：写入的文件路径列表（相对 generated/<name>/）。"""

    written: List[Path] = field(default_factory=list)


# ---------- Lancelot runtime 复制清单（07 §lancelot_runtime 复制清单） ----------

# 这些是 src/lancelot/ 下需要完整复制的子目录
_RUNTIME_DIRS = ("domain", "ports", "loop", "model_default", "channel_default")
_RUNTIME_FILES = ("errors.py",)


# ---------- 公开入口 ----------


def generate(
    state: AssemblerState,
    *,
    force: bool = False,
    lancelot_src: Path | None = None,
    templates_dir: Path | None = None,
) -> GenerateReport:
    """把 `state.selection` 烘进 `state.output_root/state.name/`。

    Args:
        state: 已由 select 填充的 AssemblerState（必须有 `name` 和 `selection`）。
        force: 目标目录已存在时是否覆盖。
        lancelot_src: Lancelot runtime 源目录（默认从 generator.py 位置推出）。
        templates_dir: Jinja2 模板目录（默认从 generator.py 位置推出）。

    Returns:
        GenerateReport：写入的文件路径列表。

    Raises:
        OutputDirExistsError: 目标目录已存在且未加 --force。
        CopyFailedError: shutil 操作失败。
        TemplateRenderFailedError: 模板渲染失败。
    """
    if not state.name:
        raise OutputDirExistsError(
            "E_OUTPUT_DIR_EXISTS: state.name is None; specify --name"
        )
    if not state.selection:
        raise OutputDirExistsError(
            "E_OUTPUT_DIR_EXISTS: state.selection is empty; nothing to compose"
        )

    if lancelot_src is None:
        lancelot_src = _default_lancelot_src()
    if templates_dir is None:
        templates_dir = _default_templates_dir()

    target = state.output_root / state.name

    # 1. 处理目标目录
    if target.exists():
        if not force:
            raise OutputDirExistsError(
                f"E_OUTPUT_DIR_EXISTS: '{target}' already exists; pass --force to overwrite"
            )
        try:
            shutil.rmtree(target)
        except OSError as e:
            raise CopyFailedError(
                f"E_COPY_FAILED: cannot remove existing target '{target}': {e}"
            ) from e

    # 2. 创建骨架
    try:
        target.mkdir(parents=True)
        (target / "app").mkdir()
        (target / "lancelot_runtime").mkdir()
        (target / "adapters").mkdir()
    except OSError as e:
        raise CopyFailedError(f"E_COPY_FAILED: cannot create target dirs: {e}") from e

    report = GenerateReport()

    # 3. 复制 Lancelot runtime 子集
    try:
        for sub in _RUNTIME_DIRS:
            src = lancelot_src / sub
            if not src.is_dir():
                raise CopyFailedError(
                    f"E_COPY_FAILED: runtime source '{src}' missing or not a directory"
                )
            _copytree(src, target / "lancelot_runtime" / sub)
            report.written.append(Path("lancelot_runtime") / sub)

        for fname in _RUNTIME_FILES:
            src = lancelot_src / fname
            if not src.is_file():
                raise CopyFailedError(
                    f"E_COPY_FAILED: runtime file '{src}' missing"
                )
            shutil.copy(src, target / "lancelot_runtime" / fname)
            report.written.append(Path("lancelot_runtime") / fname)

        # runtime 包根 __init__.py（空）
        (target / "lancelot_runtime" / "__init__.py").write_text("")
        report.written.append(Path("lancelot_runtime") / "__init__.py")
    except CopyFailedError:
        raise
    except OSError as e:
        raise CopyFailedError(f"E_COPY_FAILED: runtime copy failed: {e}") from e

    # 4. 复制选中 adapter
    try:
        for adapter in state.selection:
            rel = Path(*adapter.id.split("."))
            src = state.adapters_root / rel
            if not src.is_dir():
                raise CopyFailedError(
                    f"E_COPY_FAILED: adapter source '{src}' missing"
                )
            _copytree(src, target / "adapters" / rel)
            report.written.append(Path("adapters") / rel)
    except CopyFailedError:
        raise
    except OSError as e:
        raise CopyFailedError(f"E_COPY_FAILED: adapter copy failed: {e}") from e

    # 5. 渲染模板
    _render_all(state, target, templates_dir, report)

    return report


# ---------- 模板渲染 ----------


def _render_all(
    state: AssemblerState,
    target: Path,
    templates_dir: Path,
    report: GenerateReport,
) -> None:
    """渲染并写入 5 个模板到 target。"""
    try:
        env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=False,         # Python / TOML / YAML 文本不 escape
            keep_trailing_newline=True,
            undefined=StrictUndefined,  # 漏传上下文立即报错
        )
    except Exception as e:
        raise TemplateRenderFailedError(
            f"E_TEMPLATE_RENDER_FAILED: cannot load templates from '{templates_dir}': {e}"
        ) from e

    adapters: List[Adapter] = state.selection
    ctx = {
        "name": state.name,
        "adapters": adapters,
        "memory_count": sum(1 for a in adapters if a.category == "memory"),
        "tool_count": sum(1 for a in adapters if a.category == "tools"),
        "timestamp": _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    renderings = [
        ("composition.py.j2", "composition.py"),
        ("main.py.j2",         "app/main.py"),
        ("config.yaml.j2",     "config.yaml"),
        ("README.md.j2",       "README.md"),
        ("pyproject.toml.j2",  "pyproject.toml"),
    ]

    # app/__init__.py 是空文件，让 app/ 成为 Python 包
    _write_text(target / "app" / "__init__.py", "", report, Path("app") / "__init__.py")

    for tpl_name, out_rel in renderings:
        _render_one(env, tpl_name, target / out_rel, ctx, report, Path(out_rel))


def _render_one(
    env: "Environment",
    tpl_name: str,
    out_path: Path,
    ctx: dict,
    report: GenerateReport,
    report_rel: Path,
) -> None:
    """加载一个 jinja 模板、渲染、写到 out_path；任意 IO / 渲染失败 → TemplateRenderFailedError。"""
    try:
        rendered = env.get_template(tpl_name).render(**ctx)
    except Exception as e:
        raise TemplateRenderFailedError(
            f"E_TEMPLATE_RENDER_FAILED: cannot load/render '{tpl_name}': {e}"
        ) from e
    _write_text(out_path, rendered, report, report_rel)


def _write_text(out_path: Path, content: str, report: GenerateReport, report_rel: Path) -> None:
    """写一个文本文件并登记到 report。"""
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
    except OSError as e:
        raise TemplateRenderFailedError(
            f"E_TEMPLATE_RENDER_FAILED: cannot write '{out_path}': {e}"
        ) from e
    report.written.append(report_rel)


# ---------- 路径推导 ----------


def _copytree(src: Path, dst: Path) -> None:
    """shutil.copytree 包一层：忽略 __pycache__ 与 .pyc，避免污染生成物。"""
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def _default_lancelot_src() -> Path:
    """generator.py 在 src/lancelot/application/generator.py → 父级父级父级 = src/lancelot/。

    layout:  generator.py → application/ → lancelot/ → src/
    """
    return Path(__file__).resolve().parent.parent


def _default_templates_dir() -> Path:
    """templates/ 在 application/ 下。"""
    return Path(__file__).resolve().parent / "templates"


# ---------- CLI 辅助 ----------


def print_report(report: GenerateReport, file=sys.stdout) -> None:
    """把写入的文件路径一行行打到 file（默认 stdout）。"""
    for p in report.written:
        print(f"  wrote: {p}", file=file)
