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
from typing import Sequence

import lancelot
from lancelot.application.generator import (
    CopyFailedError,
    OutputDirExistsError,
    TemplateRenderFailedError,
    generate,
    print_report as print_generate_report,
)
from lancelot.application.launcher import (
    GeneratedDirMissingError,
    MainPyMissingError,
    launch,
)
from lancelot.application.registry import Registry
from lancelot.application.runner import run as bare_run
from lancelot.application.scanner import (
    print_report as print_scan_report,
    scan,
)
from lancelot.application.selector import (
    AdapterNotFoundError,
    DuplicateIdInSelectionError,
    select,
    print_selection,
)
from lancelot.application.state import AssemblerState
from lancelot.errors import (
    ConflictError,
    DuplicateIdError,
    GenerateError,
    LancelotError,
    RequireNotMetError,
)


# ---------- 退出码 ----------


EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_DUPLICATE_ID = 2
EXIT_SELECT = 3
EXIT_GENERATE = 4
EXIT_LAUNCH = 5


# ---------- 入口 ----------


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

    sub = parser.add_subparsers(dest="command", required=True)

    # scan
    p_scan = sub.add_parser(
        "scan",
        help="列出本地可用的 adapter（不执行任何 adapter 代码）",
    )
    p_scan.add_argument(
        "--adapters-root",
        type=Path,
        default=Path("./adapters"),
        help="adapter 源根目录（默认 ./adapters）",
    )

    # run
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

    # compose
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
        "--adapters-root",
        type=Path,
        default=Path("./adapters"),
    )
    p_compose.add_argument(
        "--output-root",
        type=Path,
        default=Path("./generated"),
    )

    # launch
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


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 主入口。返回退出码（0 = OK）。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "scan":
            return _cmd_scan(args)
        if args.command == "run":
            return _cmd_run(args)
        if args.command == "compose":
            return _cmd_compose(args)
        if args.command == "launch":
            return _cmd_launch(args)
    except LancelotError as e:
        print(f"lancelot: {type(e).__name__}: {e}", file=sys.stderr)
        return _exit_code_for(e)

    return EXIT_OK


# ---------- 子命令实现 ----------


def _cmd_scan(args: argparse.Namespace) -> int:
    """scan：列出本地 adapter。"""
    registry = Registry()
    report = scan(args.adapters_root, registry)

    # warning 走 stderr（机器可读 + 人可读）
    print_scan_report(report, file=sys.stderr)

    # 主体表格走 stdout
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
    # 1. 解析 --use 列表
    use_ids = list(args.use or [])
    if args.select_file is not None:
        use_ids = _load_select_file(args.select_file)
    if not use_ids:
        print(
            "lancelot: --use <id> (or --select-file) is required for compose",
            file=sys.stderr,
        )
        return EXIT_SELECT  # 空 selection 视作 select 阶段错误

    # 2. scan
    registry = Registry()
    state = AssemblerState(
        adapters_root=args.adapters_root,
        output_root=args.output_root,
        registry=registry,
    )
    scan_report = scan(state.adapters_root, registry)
    print_scan_report(scan_report, file=sys.stderr)

    # 3. select（错误码 3 由 _exit_code_for 自动映射）
    result = select(registry, use_ids)
    print_selection(result, file=sys.stdout)

    # 4. generate
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
    """按异常类型 → 退出码。

    注意顺序：launch 家族（EXIT_LAUNCH=5）必须先于 generate 家族
    （EXIT_GENERATE=4）判断，因为它们继承 GenerateError。
    """
    # launch 家族（5）
    if isinstance(e, (GeneratedDirMissingError, MainPyMissingError)):
        return EXIT_LAUNCH
    # generate 家族（4）
    if isinstance(e, (OutputDirExistsError, CopyFailedError, TemplateRenderFailedError)):
        return EXIT_GENERATE
    # select 家族（3）
    if isinstance(e, (AdapterNotFoundError, DuplicateIdInSelectionError,
                      RequireNotMetError, ConflictError)):
        return EXIT_SELECT
    # scan 家族（2）
    if isinstance(e, DuplicateIdError):
        return EXIT_DUPLICATE_ID
    # fallback（其它 GenerateError / 未分类 LancelotError）
    if isinstance(e, GenerateError):
        return EXIT_GENERATE
    return EXIT_GENERIC
