"""Lancelot 错误家族。

> 03-端口契约.md §"错误体系"
>
> 所有 Lancelot 异常继承 `LancelotError`。裸 `Exception` 禁止穿透到用户层。
>
> 错误分类原则：
> - 装配阶段（scan/select/generate）→ `LancelotConfigError` / `LancelotAdaptersError`
> - 启动阶段（launch）              → `GenerateError`
> - 运行阶段（生成物运行）          → `LancelotRuntimeError`

设计要点：
- 不使用 `pass`，给每个类一行 docstring（哪怕是占位）
- 全部继承链一层不漏，cli.py 可按异常类型精确分发退出码
"""
from __future__ import annotations


# ---------- 根 ----------


class LancelotError(Exception):
    """Lancelot 错误根。所有 Lancelot 异常必须继承本类。"""


# ---------- 装配阶段：配置 / manifest ----------


class LancelotConfigError(LancelotError):
    """配置错误（manifest 字段错、参数错、CLI 参数错）。"""


class ManifestError(LancelotConfigError):
    """Manifest 解析/校验失败。"""


class ManifestMissingError(ManifestError):
    """E_MANIFEST_MISSING：目录下找不到 MANIFEST.toml。"""


class ManifestParseError(ManifestError):
    """E_MANIFEST_PARSE：TOML 语法错（tomllib 抛错）。"""


class ManifestInvalidError(ManifestError):
    """E_MANIFEST_INVALID：schema 校验失败（缺字段、类型错、ID 与目录不一致等）。"""


class ManifestKindMismatchError(ManifestError):
    """E_KIND_MISMATCH：顶层表头不是 [adapter]（V1 仅接受此一种）。"""


# ---------- 端口地址 / Registry ----------


class LancelotPortAddressError(LancelotError):
    """端口契约违反。"""


class PortContractViolation(LancelotPortAddressError):
    """实现不满足端口（缺方法、签名错）。"""


class RegistryError(LancelotPortAddressError):
    """Registry 协议违反（如 ID 重复注册）。"""


class DuplicateIdError(RegistryError):
    """E_DUPLICATE_ID：同一 ID 在多处出现（多发生在 scan 阶段跨 adapter 重复）。"""


# ---------- 装配阶段：adapter 选择 ----------


class LancelotAdaptersError(LancelotError):
    """adapters/ 操作错误（resolve 失败、conflict 触发等）。"""


class RequireNotMetError(LancelotAdaptersError):
    """E_REQUIRE_NOT_MET：选中 adapter 的 requires 端口没人提供。"""


class ConflictError(LancelotAdaptersError):
    """E_CONFLICT：选中 adapter 包含 manifest.conflicts 中的互斥项。"""


class AdapterNotFoundError(LancelotAdaptersError):
    """E_ADAPTER_NOT_FOUND：--use 指定了 registry 中不存在的 ID。"""


class DuplicateIdInSelectionError(LancelotAdaptersError):
    """E_DUPLICATE_ID_IN_SELECTION：同一 ID 在 --use 中出现两次。"""


# ---------- 启动阶段：generate / launch ----------


class GenerateError(LancelotError):
    """generate / launch 阶段失败（目标目录、复制、模板渲染等）。"""


class OutputDirExistsError(GenerateError):
    """E_OUTPUT_DIR_EXISTS：目标生成目录已存在。"""


class CopyFailedError(GenerateError):
    """E_COPY_FAILED：runtime / adapter 复制失败（IO 错、权限错等）。"""


class TemplateRenderFailedError(GenerateError):
    """E_TEMPLATE_RENDER_FAILED：模板渲染或写入失败。"""


class GeneratedDirMissingError(GenerateError):
    """E_GENERATED_DIR_MISSING：generated/<name>/ 不存在。"""


class MainPyMissingError(GenerateError):
    """E_MAIN_PY_MISSING：生成物目录下找不到 app/main.py。"""


# ---------- 运行阶段：生成物运行时 ----------


class LancelotRuntimeError(LancelotError):
    """生成物运行时报错（model/tool/memory/channel/loop）。"""


class ModelError(LancelotRuntimeError):
    """ModelPort 实现抛的错误。由 Lancelot 内部的 model_default/ 抛。"""


class MemoryError(LancelotRuntimeError):
    """MemoryPort 实现抛的错误（adapter 也可抛，但必须继承本类）。"""


class ToolError(LancelotRuntimeError):
    """ToolPort 实现抛的错误。"""


class ChannelError(LancelotRuntimeError):
    """ChannelPort 实现抛的错误。由 Lancelot 内部的 channel_default/ 抛。"""


class LoopError(LancelotRuntimeError):
    """Lancelot 内部 single_loop 抛的错误。不来自任何端口实现。"""
