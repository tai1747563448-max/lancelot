"""scan 动作：把 adapters/ 下每个目录的 MANIFEST.toml 读出来，校验后塞进 Registry。

> 04-装配器协议.md §"动作 1：scan"
> 02-Manifest协议.md §"scan 阶段如何使用"

关键纪律（V1 不变量）：
- **scan 不执行任何 adapter 代码**：仅读 `MANIFEST.toml`，绝不 `import` 或 `__init__.py`
- 多次调用结果一致
- scan 不修改文件系统任何内容

错误处理（04 §动作 1 错误处理表）：
- E_MANIFEST_MISSING / E_MANIFEST_PARSE / E_MANIFEST_INVALID /
  E_KIND_MISMATCH / E_CATEGORY_MISMATCH：跳过该目录，warning，继续扫下一个
- E_RESERVED_PORT：**warning**（不跳过）
- E_DUPLICATE_ID：整个 scan 失败，退出码 2
"""
from __future__ import annotations

import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from lancelot.application.registry import Registry
from lancelot.domain.types import Adapter, Capability
from lancelot.errors import (
    DuplicateIdError,
    ManifestInvalidError,
    ManifestKindMismatchError,
    ManifestMissingError,
    ManifestParseError,
)


# ---------- V1 常量 ----------

# 02 §"[adapter] id"：`^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$`
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")

# 02 §"[adapter] category" 枚举：V1 仅 memory / tools
_VALID_CATEGORIES = ("memory", "tools")

# 02 §"保留端口"：ModelPort / ChannelPort 由 Lancelot 内部提供
_RESERVED_PORTS = ("ModelPort", "ChannelPort")

# 02 §"[capabilities] provides" V1 允许集合
_VALID_PROVIDES = ("MemoryPort", "ToolPort")


# ---------- 报告对象 ----------


@dataclass(frozen=True)
class ScanWarning:
    """scan 阶段产出的非致命告警（不影响该 adapter 是否进入 Registry）。"""

    code: str           # 错误码字符串，例如 "E_RESERVED_PORT"
    message: str        # 人类可读
    adapter_dir: Path   # 出问题的 adapter 目录


@dataclass
class ScanReport:
    """scan 的全部产物：warning 列表 + 实际进入 Registry 的 adapter 列表。"""

    warnings: List[ScanWarning] = field(default_factory=list)
    registered: List[Adapter] = field(default_factory=list)


# ---------- 公开入口 ----------


def _warn(report: ScanReport, code: str, message: str, adapter_dir: Path) -> None:
    """把一条 warning 追加到 report。集中在此便于统一扩展（如统计、过滤）。"""
    report.warnings.append(ScanWarning(code=code, message=message, adapter_dir=adapter_dir))


def scan(adapters_root: Path, registry: Registry) -> ScanReport:
    """扫描 `adapters_root` 下所有一级目录，填充 `registry`。

    Args:
        adapters_root: 用户指定的 adapter 源根目录（默认 `./adapters`）。
        registry: 装配器维护的全局 Registry 实例（in-place 填充）。

    Returns:
        ScanReport：warning 与注册成功的 adapter 列表。

    Raises:
        DuplicateIdError: 两个 adapter 声明了同一个 ID（整次 scan 失败）。

    Notes:
        - adapters_root 不存在 → 视为空 scan，warning 一次，返回空报告
        - 顶层非目录项（散落文件）→ 静默忽略
    """
    report = ScanReport()

    if not adapters_root.exists():
        _warn(
            report,
            "E_ADAPTERS_ROOT_MISSING",
            f"adapters root '{adapters_root}' does not exist; nothing to scan",
            adapters_root,
        )
        return report

    if not adapters_root.is_dir():
        _warn(
            report,
            "E_ADAPTERS_ROOT_NOT_DIR",
            f"adapters root '{adapters_root}' is not a directory",
            adapters_root,
        )
        return report

    # V1 layout：adapters/<category>/<name>/. scanner 接受 ≤ 2 层深度：
    # - 一级：adapters/<name>/（散落 adapter；少见但允许）
    # - 两级：adapters/<category>/<name>/（标准 layout）
    # 纯分类目录（不含 MANIFEST.toml 但含子目录）静默跳过
    candidates = _discover_candidates(adapters_root)

    for adapter_dir in candidates:
        # DuplicateIdError → 整次 scan 失败（04 §动作 5）
        _scan_one(adapter_dir, adapters_root, registry, report)

    return report


# ---------- 目录发现 ----------


def _discover_candidates(adapters_root: Path) -> List[Path]:
    """找出所有含 MANIFEST.toml 的 adapter 目录（V1 layout ≤ 2 层）。

    V1 标准 layout：`adapters/<category>/<name>/`。
    兼容 layout：`adapters/<name>/`（散落 adapter）。
    纯分类目录（不含 MANIFEST.toml 但含子目录的）静默跳过。
    """
    candidates: List[Path] = []
    for entry in sorted(
        p for p in adapters_root.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    ):
        if (entry / "MANIFEST.toml").is_file():
            # 一级 adapter
            candidates.append(entry)
            continue
        # 否则视为分类目录：扫它的子目录
        for sub in sorted(
            p for p in entry.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        ):
            if (sub / "MANIFEST.toml").is_file():
                candidates.append(sub)
            # 没 MANIFEST.toml 的子目录 → 静默跳过（不 warning）
    return candidates


# ---------- 单个 adapter 处理 ----------


def _scan_one(
    adapter_dir: Path,
    adapters_root: Path,
    registry: Registry,
    report: ScanReport,
) -> None:
    """扫描单个 adapter 目录；失败按 04 协议记 warning 并继续。"""
    manifest_path = adapter_dir / "MANIFEST.toml"

    if not manifest_path.is_file():
        _warn(
            report,
            "E_MANIFEST_MISSING",
            f"MANIFEST.toml not found in '{adapter_dir}'",
            adapter_dir,
        )
        return

    # 1. TOML 解析
    try:
        with manifest_path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        _warn(
            report,
            "E_MANIFEST_PARSE",
            f"TOML parse error in '{manifest_path}': {e}",
            adapter_dir,
        )
        return

    # 2. 顶层表头校验：V1 只接受 [adapter]
    if "adapter" not in data:
        _warn(
            report,
            "E_KIND_MISMATCH",
            f"top-level table must be [adapter] in '{manifest_path}' "
            f"(V1 does not accept [plugin])",
            adapter_dir,
        )
        return

    # 3. schema 校验 + 构造 Adapter
    try:
        adapter = _parse_manifest(data, adapter_dir, adapters_root)
    except ManifestKindMismatchError as e:
        _warn(report, "E_KIND_MISMATCH", str(e), adapter_dir)
        return
    except ManifestInvalidError as e:
        _warn(report, "E_MANIFEST_INVALID", str(e), adapter_dir)
        return

    # 4. reserved port 检查：warning 不跳过
    for cap in adapter.provides:
        if cap.name in _RESERVED_PORTS:
            _warn(
                report,
                "E_RESERVED_PORT",
                f"adapter '{adapter.id}' declares reserved port "
                f"'{cap.name}' (reserved by Lancelot, not allowed in V1)",
                adapter_dir,
            )

    # 5. 注册：duplicate 整次失败
    #    registry.register 抛 DuplicateIdError（RegistryError 子类），
    #    这里是 scan 阶段最常见的失败——让整次 scan 失败、退出码 2。
    registry.register(adapter)

    report.registered.append(adapter)


# ---------- manifest 解析 ----------


def _parse_manifest(
    data: dict,
    adapter_dir: Path,
    adapters_root: Path,
) -> Adapter:
    """把 TOML dict 解析成 Adapter dataclass。

    Raises:
        ManifestInvalidError: 字段缺失、类型错、ID 与目录不一致等。
        ManifestKindMismatchError: 顶层表头是 [plugin]（V1 非法）。
    """
    # 顶层如果同时含 [plugin]，按 02 §"顶层表头"视为 E_KIND_MISMATCH
    if "plugin" in data:
        raise ManifestKindMismatchError(
            f"top-level [plugin] is not accepted in V1 (file: {adapter_dir / 'MANIFEST.toml'})"
        )

    a = data.get("adapter")
    if not isinstance(a, dict):
        raise ManifestInvalidError("[adapter] table missing or not a table")

    e = data.get("entry")
    if not isinstance(e, dict):
        raise ManifestInvalidError("[entry] table missing or not a table")

    c = data.get("capabilities")
    if not isinstance(c, dict):
        raise ManifestInvalidError("[capabilities] table missing or not a table")

    # ----- [adapter] 必填字段 -----
    aid = a.get("id")
    if not isinstance(aid, str):
        raise ManifestInvalidError("[adapter].id missing or not a string")
    if not _ID_PATTERN.match(aid):
        raise ManifestInvalidError(
            f"[adapter].id '{aid}' does not match pattern "
            f"'<category>.<name>' (lowercase, dot-separated)"
        )

    # ID 与目录布局强绑定（02 §"[adapter] id"）
    expected_rel = Path(*aid.split("."))
    actual_rel = adapter_dir.relative_to(adapters_root)
    if actual_rel != expected_rel:
        raise ManifestInvalidError(
            f"[adapter].id '{aid}' implies path '{expected_rel}', "
            f"but adapter lives at '{actual_rel}'"
        )

    name = a.get("name")
    if not isinstance(name, str) or len(name) > 64:
        raise ManifestInvalidError("[adapter].name missing or > 64 chars")

    version = a.get("version")
    if not isinstance(version, str):
        raise ManifestInvalidError("[adapter].version missing or not a string")

    category = a.get("category")
    if category not in _VALID_CATEGORIES:
        raise ManifestKindMismatchError(
            f"[adapter].category '{category}' not in V1 set {_VALID_CATEGORIES}"
        )
    # category 与目录前缀一致
    if actual_rel.parts[0] != category:
        raise ManifestInvalidError(
            f"[adapter].category '{category}' does not match directory prefix "
            f"'{actual_rel.parts[0]}'"
        )

    description = a.get("description")
    if not isinstance(description, str) or len(description) > 256:
        raise ManifestInvalidError("[adapter].description missing or > 256 chars")

    min_framework = a.get("min_framework")
    if not isinstance(min_framework, str):
        raise ManifestInvalidError("[adapter].min_framework missing or not a string")

    # ----- [entry] 必填字段 -----
    entry_module = e.get("module")
    if not isinstance(entry_module, str):
        raise ManifestInvalidError("[entry].module missing or not a string")

    entry_factory = e.get("factory")
    if not isinstance(entry_factory, str):
        raise ManifestInvalidError("[entry].factory missing or not a string")

    # ----- [capabilities] -----
    provides_raw = c.get("provides", [])
    if not isinstance(provides_raw, list) or not provides_raw:
        raise ManifestInvalidError(
            "[capabilities].provides must be a non-empty list of port names"
        )
    for p in provides_raw:
        if not isinstance(p, str):
            raise ManifestInvalidError("[capabilities].provides must be list[str]")

    provides = [Capability(name=p, version="1.0.0") for p in provides_raw]
    requires = [Capability(name=r, version="1.0.0") for r in c.get("requires", [])]
    conflicts = list(c.get("conflicts", []))
    enhances = list(c.get("enhances", []))

    for conf in conflicts + enhances:
        if not isinstance(conf, str):
            raise ManifestInvalidError(
                "[capabilities].conflicts/enhances must be list[str]"
            )

    # ----- [config] -----
    cfg = data.get("config", {})
    if not isinstance(cfg, dict):
        raise ManifestInvalidError("[config] must be a table")
    schema = cfg.get("schema", {})
    if not isinstance(schema, dict):
        raise ManifestInvalidError("[config].schema must be a table")

    # V1 简化：[config].schema 中字段约束的形式是
    # `{ type = "int", default = 1024, required = false }`，此处不展开校验，
    # 只保证是 table。实例化时由 generator 套用默认值。
    return Adapter(
        id=aid,
        name=name,
        version=version,
        category=category,
        description=description,
        min_framework=min_framework,
        entry_module=entry_module,
        entry_factory=entry_factory,
        provides=provides,
        requires=requires,
        conflicts=conflicts,
        enhances=enhances,
        config_schema=schema,
    )


# ---------- CLI 辅助 ----------


def print_report(report: ScanReport, file=sys.stderr) -> None:
    """把 warning 一行行打到 file（默认 stderr），CLI 调用。"""
    for w in report.warnings:
        print(f"[{w.code}] {w.message}", file=file)
