"""Lancelot CLI——装配器的用户入口。

> 04-装配器协议.md §"CLI 完整命令清单（V1）"
>
>     lancelot scan                          # 列出 adapter
>     lancelot run [--config <path>]         # bare 模式直接跑
>     lancelot compose --use <id>... --name <name> [--force] [--select-file <path>]
>     lancelot launch <generated-name>       # 启动已生成的 framework
>     lancelot --version / --help

错误 → 退出码（按 04 §错误处理表聚合）：
- 0  OK
- 1  未分类错误（其它 LancelotError）
- 2  E_DUPLICATE_ID                              (scan)
- 3  E_ADAPTER_NOT_FOUND / E_REQUIRE_NOT_MET /
     E_CONFLICT / E_DUPLICATE_ID_IN_SELECTION   (select)
- 4  E_OUTPUT_DIR_EXISTS / E_COPY_FAILED /
     E_TEMPLATE_RENDER_FAILED                    (generate)
- 5  E_GENERATED_DIR_MISSING / E_MAIN_PY_MISSING (launch)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Dict, Sequence

import lancelot
from lancelot.application.generator import (
    generate,
    print_report as print_generate_report,
)
from lancelot.application.launcher import launch
from lancelot.application.registry import Registry
from lancelot.application.runner import run as bare_run
from lancelot.application.scanner import (
    print_report as print_scan_report,
    scan,
)
from lancelot.application.selector import select, print_selection
from lancelot.application.state import AssemblerState
from lancelot.errors import (
    AdapterNotFoundError,
    ConflictError,
    CopyFailedError,
    DuplicateIdError,
    DuplicateIdInSelectionError,
    GenerateError,
    GeneratedDirMissingError,
    LancelotError,
    MainPyMissingError,
    OutputDirExistsError,
    RequireNotMetError,
    TemplateRenderFailedError,
)


# ---------- 退出码 ----------


EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_DUPLICATE_ID = 2
EXIT_SELECT = 3
EXIT_GENERATE = 4
EXIT_LAUNCH = 5

# 异常族 → 退出码映射表。**顺序很重要**：launch 家族（EXIT_LAUNCH=5）必须
# 先于 generate 家族（EXIT_GENERATE=4）判断，因为前者继承后者。
_EXIT_CODE_TABLE = (
    (EXIT_LAUNCH, (GeneratedDirMissingError, MainPyMissingError)),
    (EXIT_GENERATE, (OutputDirExistsError, CopyFailedError, TemplateRenderFailedError)),
    (EXIT_SELECT, (AdapterNotFoundError, DuplicateIdInSelectionError, RequireNotMetError, ConflictError)),
    (EXIT_DUPLICATE_ID, (DuplicateIdError,)),
)


# ---------- argparse 构造 ----------


def build_parser() -> argparse.ArgumentParser:
    """构造 argparse。单独抽出来便于测试。"""
    parser = argparse.ArgumentParser(
        prog="lancelot",
        description="Lancelot 元框架 V1 装配器",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"lancelot {lancelot.__version__}",
    )
    # 全局参数：--adapters-root 给 scan/compose 用；run/launch 不读，
    # 但放在顶层避免子命令间不一致。
    parser.add_argument(
        "--adapters-root",
        type=Path,
        default=Path("./adapters"),
        help="adapter 源根目录（默认 ./adapters；scan/compose 用）",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "scan",
        help="列出本地可用的 adapter（不执行任何 adapter 代码）",
    )

    p_run = sub.add_parser(
        "run",
        help="bare Lancelot 直接跑（不接 adapter；不写文件）",
    )
    p_run.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Lancelot 内部默认实现的配置（V1 mock 可选）",
    )
    p_run.add_argument(
        "--max-turns",
        type=int,
        default=10,
        help="单次循环最大步数（默认 10）",
    )

    p_compose = sub.add_parser(
        "compose",
        help="把选中的 adapter 烘进 generated/<name>/",
    )
    p_compose.add_argument(
        "--use",
        action="append",
        default=[],
        metavar="ID",
        help="要包含的 adapter id（可多次指定）",
    )
    p_compose.add_argument(
        "--name",
        required=True,
        help="生成物子目录名",
    )
    p_compose.add_argument(
        "--force",
        action="store_true",
        help="覆盖已存在目标",
    )
    p_compose.add_argument(
        "--select-file",
        type=Path,
        default=None,
        help="从 YAML 读 --use 列表（文件含 'use: [...]' 键）",
    )
    p_compose.add_argument(
        "--output-root",
        type=Path,
        default=Path("./generated"),
    )

    p_launch = sub.add_parser(
        "launch",
        help="启动已生成的 framework（等价于 cd generated/<name> && python -m app.main）",
    )
    p_launch.add_argument(
        "name",
        help="生成物子目录名",
    )
    p_launch.add_argument(
        "--output-root",
        type=Path,
        default=Path("./generated"),
    )
    p_launch.add_argument(
        "--python",
        default=None,
        help="Python 解释器路径（默认 sys.executable）",
    )

    return parser


# ---------- 子命令实现 ----------


def _cmd_scan(args: argparse.Namespace) -> int:
    """scan：列出本地 adapter。"""
    registry = Registry()
    report = scan(args.adapters_root, registry)
    print_scan_report(report, file=sys.stderr)

    adapters = registry.all()
    print(f"{'id':<28} {'name':<24} {'version':<10} {'category':<10} capabilities")
    for a in adapters:
        caps = ",".join(c.name for c in a.provides)
        print(f"{a.id:<28} {a.name:<24} {a.version:<10} {a.category:<10} [{caps}]")

    print()
    print(
        f"Scanned {len(report.registered) + len(report.warnings)} adapters, "
        f"{len(report.registered)} OK, {len(report.warnings)} warnings."
    )
    return EXIT_OK


def _cmd_run(args: argparse.Namespace) -> int:
    """run：bare 模式直接跑。退出码由 bare_run 自己返回。"""
    return bare_run(config_path=args.config, max_turns=args.max_turns)


def _cmd_compose(args: argparse.Namespace) -> int:
    """compose：scan → select → generate。"""
    use_ids = list(args.use or [])
    if args.select_file is not None:
        use_ids = _load_select_file(args.select_file)
    if not use_ids:
        print(
            "lancelot: --use <id> (or --select-file) is required for compose",
            file=sys.stderr,
        )
        return EXIT_SELECT

    registry = Registry()
    state = AssemblerState(
        adapters_root=args.adapters_root,
        output_root=args.output_root,
        registry=registry,
    )
    scan_report = scan(state.adapters_root, registry)
    print_scan_report(scan_report, file=sys.stderr)

    result = select(registry, use_ids)
    print_selection(result, file=sys.stdout)

    state.selection = result.selection
    state.name = args.name
    gen_report = generate(state, force=args.force)

    target = state.output_root / state.name
    print(f"Generated {target}/", file=sys.stdout)
    print_generate_report(gen_report, file=sys.stdout)
    return EXIT_OK


def _cmd_launch(args: argparse.Namespace) -> int:
    """launch：fork-exec 子进程跑生成物。退出码透传给 caller。"""
    return launch(
        args.output_root,
        args.name,
        python_executable=args.python,
    )


# ---------- 子命令分派 ----------


_DISPATCH: Dict[str, Callable[[argparse.Namespace], int]] = {
    "scan": _cmd_scan,
    "run": _cmd_run,
    "compose": _cmd_compose,
    "launch": _cmd_launch,
}


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 主入口。返回退出码（0 = OK）。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return _DISPATCH[args.command](args)
    except LancelotError as e:
        print(f"lancelot: {type(e).__name__}: {e}", file=sys.stderr)
        return _exit_code_for(e)


# ---------- 工具 ----------


def _load_select_file(path: Path) -> list[str]:
    """从 YAML 文件读 --use 列表。文件格式：`use: [id1, id2, ...]`。"""
    import yaml  # 延迟导入：run 子命令不需要 yaml
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "use" not in data:
        raise ValueError(
            f"select-file '{path}' must be a YAML mapping with a 'use' key"
        )
    use = data["use"]
    if not isinstance(use, list) or not all(isinstance(x, str) for x in use):
        raise ValueError(f"select-file '{path}': 'use' must be a list[str]")
    return list(use)


def _exit_code_for(e: LancelotError) -> int:
    """按异常类型 → 退出码。"""
    for code, types in _EXIT_CODE_TABLE:
        if isinstance(e, types):
            return code
    # 兜底：未在表中登记的 GenerateError 子类仍归 generate 家族
    if isinstance(e, GenerateError):
        return EXIT_GENERATE
    return EXIT_GENERIC