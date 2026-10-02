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
from lancelot.errors import GenerateError, LancelotError


# ---------- 本地异常（04 错误码表里有，03 错误家族未细列） ----------


class OutputDirExistsError(GenerateError):
    """E_OUTPUT_DIR_EXISTS：目标生成目录已存在。"""


class CopyFailedError(GenerateError):
    """E_COPY_FAILED：runtime / adapter 复制失败（IO 错、权限错等）。"""


class TemplateRenderFailedError(GenerateError):
    """E_TEMPLATE_RENDER_FAILED：模板渲染或写入失败。"""


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
            shutil.copytree(src, target / "lancelot_runtime" / sub)
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
            dst = target / "adapters" / rel
            shutil.copytree(src, dst)
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

    # 通用上下文
    adapters: List[Adapter] = state.selection
    memory_count = sum(1 for a in adapters if a.category == "memory")
    tool_count = sum(1 for a in adapters if a.category == "tools")
    ctx = {
        "name": state.name,
        "adapters": adapters,
        "memory_count": memory_count,
        "tool_count": tool_count,
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
    try:
        (target / "app" / "__init__.py").write_text("")
        report.written.append(Path("app") / "__init__.py")
    except OSError as e:
        raise TemplateRenderFailedError(
            f"E_TEMPLATE_RENDER_FAILED: cannot write app/__init__.py: {e}"
        ) from e

    for tpl_name, out_rel in renderings:
        try:
            tpl = env.get_template(tpl_name)
        except Exception as e:
            raise TemplateRenderFailedError(
                f"E_TEMPLATE_RENDER_FAILED: cannot load template '{tpl_name}': {e}"
            ) from e

        try:
            rendered = tpl.render(**ctx)
        except Exception as e:
            raise TemplateRenderFailedError(
                f"E_TEMPLATE_RENDER_FAILED: rendering '{tpl_name}' failed: {e}"
            ) from e

        out_path = target / out_rel
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8")
        except OSError as e:
            raise TemplateRenderFailedError(
                f"E_TEMPLATE_RENDER_FAILED: cannot write '{out_path}': {e}"
            ) from e

        report.written.append(Path(out_rel))


# ---------- 路径推导 ----------


def _default_lancelot_src() -> Path:
    """generator.py 在 src/lancelot/application/generator.py → 父级父级父级 = src/lancelot/。

    layout:  generator.py → application/ → lancelot/ → src/
    """
    return Path(__file__).resolve().parent.parent.parent


def _default_templates_dir() -> Path:
    """templates/ 在 application/ 下。"""
    return Path(__file__).resolve().parent / "templates"


# ---------- CLI 辅助 ----------


def print_report(report: GenerateReport, file=sys.stdout) -> None:
    """把写入的文件路径一行行打到 file（默认 stdout）。"""
    for p in report.written:
        print(f"  wrote: {p}", file=file)
