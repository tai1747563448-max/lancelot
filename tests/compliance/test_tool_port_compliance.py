"""ToolPort compliance tests.

> V1 判据 #6（part 2）：内置 echo adapter 必须满足 ToolPort duck-typed 契约。

Duck-typed 契约（见 src/lancelot/ports/tool.py）：
- 三个 @property：`name: str`、`description: str`、`parameters_schema: Dict`
- 一个方法：`invoke(**kwargs) -> ToolResult`（或 loop 可包装的形态）

Loop 三种可接受的 invoke 返回形态（`src/lancelot/loop/single_loop.py::_invoke_tool`）：
1. `ToolResult` 实例
2. `dict`：`{"content": <str>, "is_error": <bool>}`
3. duck-typed 对象：含 `.content` 与 `.is_error` 属性

EchoTool 当前返回 dict。本测试通过 `assert_invoke_result_wrappable` 接受任何一种形态，
以便未来 adapter 改返回 `ToolResult` 或 duck-typed 时无需改测试。
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

from lancelot.domain import ToolResult
from lancelot.errors import LancelotError, ToolError
from lancelot.ports.tool import ToolPort


# ---------- fixtures ----------


@pytest.fixture()
def tool() -> Any:
    """返回 EchoTool 实例（不依赖 isintance 检查——纯 duck typing）。"""
    # 把 adapters/ 加进 sys.path（项目不在 src 下，adapter 是相对路径模块）
    repo_root = Path(__file__).resolve().parents[2]
    adapter_dir = repo_root / "adapters" / "tools" / "echo"
    if str(adapter_dir) not in sys.path:
        sys.path.insert(0, str(adapter_dir))
    import importlib

    module = importlib.import_module("__init__")  # echo/__init__.py
    factory = getattr(module, "create_tool", None)
    if callable(factory):
        return factory()
    # 兜底：直接拿类
    return module.EchoTool()


# ---------- helpers ----------


def _extract_content_and_is_error(raw: Any) -> tuple[Any, Any]:
    """从三种 duck-typed 形态中抽出 (content, is_error)。

    不强求 ToolResult isinstance——任何一种形态都接受。
    """
    if isinstance(raw, ToolResult):
        return raw.content, raw.is_error
    if isinstance(raw, dict):
        return raw.get("content"), raw.get("is_error")
    if hasattr(raw, "content") and hasattr(raw, "is_error"):
        return raw.content, raw.is_error
    raise AssertionError(
        f"invoke() return is not a wrappable ToolResult shape: {type(raw).__name__}"
    )


# ---------- property checks (1, 2, 3) ----------


def test_name_is_non_empty_str(tool: Any) -> None:
    """`name` 是非空字符串。"""
    name = tool.name
    assert isinstance(name, str), f"name must be str, got {type(name).__name__}"
    assert len(name) > 0, "name must be non-empty"
    # 文档约定：工具名应人类可读、有意义（不需要硬匹配 "echo"——其他 adapter 可自由命名）
    assert name.strip() == name, "name must not have leading/trailing whitespace"


def test_description_is_non_empty_str(tool: Any) -> None:
    """`description` 是非空字符串。"""
    description = tool.description
    assert isinstance(description, str), (
        f"description must be str, got {type(description).__name__}"
    )
    assert len(description) > 0, "description must be non-empty"


def test_parameters_schema_is_object_dict(tool: Any) -> None:
    """`parameters_schema` 是 dict，且顶层 `type == "object"`（JSON Schema 约定）。"""
    schema = tool.parameters_schema
    assert isinstance(schema, dict), (
        f"parameters_schema must be dict, got {type(schema).__name__}"
    )
    assert schema.get("type") == "object", (
        f"parameters_schema top-level type must be 'object', got {schema.get('type')!r}"
    )


# ---------- duck-typed structural check ----------


def test_tool_satisfies_toolport_protocol_structurally(tool: Any) -> None:
    """duck-typed：tool 必须暴露 name/description/parameters_schema/invoke。

    不做 isinstance(tool, ToolPort)——Protocol 用 runtime_checkable 不强制 import，
    这里只用 hasattr 三件套验证 shape。
    """
    assert hasattr(tool, "name"), "tool must expose .name"
    assert hasattr(tool, "description"), "tool must expose .description"
    assert hasattr(tool, "parameters_schema"), "tool must expose .parameters_schema"
    assert hasattr(tool, "invoke"), "tool must expose .invoke()"
    assert callable(tool.invoke), "tool.invoke must be callable"


# ---------- invoke behaviour (5, 6, 7, 8) ----------


def test_invoke_returns_wrappable_shape(tool: Any) -> None:
    """`invoke(...)` 返回值必须能被 loop 包成 ToolResult。

    接受：ToolResult 实例 / dict{content,is_error} / duck-typed 对象。
    """
    raw = tool.invoke(test_kwarg="value")
    # 不应抛异常；下面的 helper 会在三种形态都接受的情况下不抛
    content, is_error = _extract_content_and_is_error(raw)
    assert content is not None, "wrappable result must carry content"
    assert isinstance(is_error, bool), "wrappable result.is_error must be bool"


def test_invoke_content_reflects_kwargs(tool: Any) -> None:
    """`content` 必须以某种可读方式反映 kwargs。

    具体策略：
    - 若 content 是 str 且 JSON 可解析为 dict → 必须包含传入的 kwarg
    - 若 content 是其它形态——不强求结构，只断言关键 key 在
    """
    raw = tool.invoke(test_kwarg="value")
    content, _ = _extract_content_and_is_error(raw)

    # 优先尝试 JSON 反序列化（EchoTool 用 json.dumps）
    if isinstance(content, str):
        try:
            decoded = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            decoded = None
    else:
        decoded = None

    if isinstance(decoded, dict):
        # EchoTool 的精确契约：JSON 化的 kwargs 必须含 test_kwarg="value"
        assert decoded.get("test_kwarg") == "value", (
            f"content JSON must echo the input kwarg; got {decoded!r}"
        )
    else:
        # 兜底：content 必须以 str 形式提及 key=value
        assert "key" in str(content).lower() or "value" in str(content), (
            f"content must reflect kwargs in some readable way; got {content!r}"
        )


def test_invoke_is_error_false_on_success(tool: Any) -> None:
    """成功调用时 `is_error` 必须为 False。"""
    raw = tool.invoke(test_kwarg="value")
    _, is_error = _extract_content_and_is_error(raw)
    assert is_error is False, (
        f"is_error must be False on successful invocation; got {is_error!r}"
    )


def test_invoke_with_no_kwargs_does_not_raise(tool: Any) -> None:
    """空 kwargs 调用不得抛异常。"""
    # EchoTool.invoke 对 kwargs 没有任何 required 字段
    raw = tool.invoke()
    content, is_error = _extract_content_and_is_error(raw)
    assert is_error is False
    # 内容应当是合法的（dict 形态下 `{}` 的 JSON）
    if isinstance(content, str):
        # 应能反序列化
        try:
            json.loads(content)
        except (json.JSONDecodeError, ValueError) as e:
            pytest.fail(f"empty-kwargs content must be JSON-decodable: {content!r} ({e})")


def test_invoke_with_unicode_kwargs(tool: Any) -> None:
    """非 ASCII kwargs 也能正确回显（确保 adapter 不强行 str() 化中文丢字符）。"""
    raw = tool.invoke(文本="你好")
    content, is_error = _extract_content_and_is_error(raw)
    assert is_error is False
    assert "你好" in str(content), (
        f"unicode kwargs must round-trip; got content={content!r}"
    )


# ---------- error class availability (9) ----------


def test_tool_error_class_is_importable() -> None:
    """`ToolError` 必须可从 `lancelot.errors` 导入——adapter 作者的约定错误类型。"""
    assert ToolError is not None
    # 必须继承 LancelotError（错误体系根）
    assert issubclass(ToolError, LancelotError), (
        "ToolError must inherit LancelotError to be caught by the framework"
    )
    # 必须可实例化+可抛
    err = ToolError("test")
    assert isinstance(err, LancelotError)
    with pytest.raises(ToolError):
        raise ToolError("boom")


# ---------- duck-typing discipline (10) ----------


def test_echo_adapter_does_not_import_lancelot() -> None:
    """EchoTool 模块不得 import 任何 lancelot.*——V1 强制的 duck-typed 纪律。

    验证方式：AST 解析 `adapters/tools/echo/__init__.py`，扫所有 Import / ImportFrom 节点，
    不允许 `lancelot` 出现在 module 里。
    """
    repo_root = Path(__file__).resolve().parents[2]
    adapter_path = repo_root / "adapters" / "tools" / "echo" / "__init__.py"
    assert adapter_path.exists(), f"adapter file not found: {adapter_path}"

    source = adapter_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(adapter_path))

    lancelot_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "lancelot":
                    lancelot_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == "lancelot":
                lancelot_imports.append(node.module)

    assert not lancelot_imports, (
        "EchoTool adapter must NOT import Lancelot types (duck-typed discipline). "
        f"Found: {lancelot_imports}"
    )


# ---------- lifecycle sanity ----------


def test_factory_returns_fresh_instance(tool: Any) -> None:
    """create_tool 无副作用：每次返回独立实例。"""
    import importlib

    repo_root = Path(__file__).resolve().parents[2]
    adapter_dir = repo_root / "adapters" / "tools" / "echo"
    if str(adapter_dir) not in sys.path:
        sys.path.insert(0, str(adapter_dir))
    module = importlib.import_module("__init__")

    a = module.create_tool()
    b = module.create_tool()
    assert a is not b, "create_tool must return fresh instance"
    assert a.name == b.name == tool.name