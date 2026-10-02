# 02 · Manifest 协议

> 状态：草案 v1.2（基于 2026-10-02 第二次术语校正：loop/model/channel 收回 Lancelot）
> 读者：装配器维护者、adapter 作者、合规性测试作者
> 范围：定义 V1 adapter（V1 不实现 plugin loader）源文件如何用 TOML 描述自己

---

## 这是什么

**Manifest 是一段嵌入在 adapter 源文件旁的 TOML 数据**，由装配器在 **scan 阶段**读取。它声明模块的身份、能力、依赖、入口点。装配器不读取模块的代码来获取这些信息——这条规则保证 "scan 不执行" 的安全边界。

> V1 范围说明：本协议描述的 schema 同时约束 V1 的 adapter（`adapters/`）。V1 不实现 plugin loader，`plugins/` 目录在 V1 留空。`[plugin]` 表头在 V1 视为非法（V2 起接受）。这意味着本协议的"参数约束"只对 memory 和 tools 两类生效——model/channel 的默认实现由 Lancelot 内部装到 `src/lancelot/`，不走 manifest。

## 这不是什么

- **不是配置文件**：配置是用户输入、由用户/工具改写的运行时参数。Manifest 是模块自己的身份信息，原则上只由作者维护。
- **不是代码**：Manifest 不包含可执行逻辑。如果一段逻辑必须存在才能正确组装，把它放进入口函数里。
- **不是二进制元数据**：模块以源文件存在，Manifest 是源文件的一部分，不是编译产物。

---

## 物理布局

每个 adapter 在磁盘上是 **一个目录**，目录内有两个必备文件：

```
adapters/
└── <module-name-as-path>/
    ├── MANIFEST.toml           # 必需：自描述
    └── __init__.py             # 必需：入口模块（生成阶段才被 import）
```

`<module-name-as-path>` 是模块 ID 的点号路径形式（如 `memory.inmemory` → `memory/inmemory/`）。这条规则保证"目录即 ID"，物理布局和身份一致。

### V1 真实示例（写入到 `adapters/memory/inmemory/`）

`adapters/memory/inmemory/MANIFEST.toml`：

```toml
# === Lancelot Manifest v1 ===
# 解析器：tomllib（标准库）；写回：tomli_w（仅装配器内部使用）

[adapter]
id            = "memory.inmemory"
name          = "In-Memory Memory"
version       = "0.1.0"
category      = "memory"
description   = "进程内短期记忆，不持久化。仅用于 V1 演示与测试。"
min_framework = "1.0.0"

[entry]
module  = "memory.inmemory"
factory = "create_memory"

[capabilities]
provides = ["MemoryPort"]
requires = []
conflicts = []
enhances = []

[config]
schema = { max_entries = { type = "int", default = 1024, required = false } }
```

`adapters/memory/inmemory/__init__.py`：

```python
"""memory.inmemory —— 满足 MemoryPort 的最小实现。"""

from .adapter import create_memory

__all__ = ["create_memory"]
```

### 模块路径解析规则

`[entry].module` 是从 `adapters/` 根目录开始算的虚线模块路径：

- `adapters/` 在 Lancelot 运行时被加到 `sys.path`（import `memory.inmemory`）
- `plugins/` V1 不在 Lancelot 运行时被加（V1 不读 plugins/目录）

V1 不存在 `adapters/<id>/` 与 `plugins/<id>/` 同名的情况，因为 V1 不接受任何 plugin。

---

## TOML Schema（v1）

Manifest 顶层有 4 个 table：`[adapter]`、`[entry]`、`[capabilities]`、`[config]`。

### 顶层表头：[adapter]

V1 manifest **只能**用 `[adapter]` 顶层表头。

- `adapters/<id>/MANIFEST.toml` 顶层用 `[adapter]` → 通过
- `adapters/<id>/MANIFEST.toml` 顶层用 `[plugin]` → 报错 `E_KIND_MISMATCH`
- V1 不扫 `plugins/` 目录；如果文件被扫描到，对应 manifest 表头必须是 `[plugin]`，否则报 `E_KIND_MISMATCH`

> V2 plugin loader 引入时，V2 起接受 `[plugin]` 顶层表头。V1 schema 设计与 V2 plugin schema **向前兼容**（V2 时只需新增 `[plugin]` 接受，不破坏 V1 schema）。

### `[adapter]` —— 身份

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `id` | string | ✅ | 形如 `<category>.<name>`，全局唯一，正则 `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$` |
| `name` | string | ✅ | 人类可读，<= 64 字符 |
| `version` | string | ✅ | SemVer `MAJOR.MINOR.PATCH`，可选预发布标签 |
| `category` | string | ✅ | 枚举：`memory` / `tools`（V1 仅这两个；`model`、`agent` 在 V1 不接受，因为这两块没有 adapter） |
| `description` | string | ✅ | 人类可读，<= 256 字符 |
| `min_framework` | string | ✅ | Lancelot 主版本约束（如 `"1.0.0"`，V1 简化为字符串等值匹配） |

`id` 与目录布局强绑定：模块 ID 是 `memory.inmemory`，物理目录必须是 `adapters/memory/inmemory/`。这条规则让"忘记改 manifest 但改了目录"这种漂移立即可见。

`category` 在 V1 与目录前缀必须一致：

- `category = "memory"` → 物理目录必须是 `adapters/memory/<name>/`
- `category = "tools"` → 物理目录必须是 `adapters/tools/<name>/`

### `[entry]` —— 入口点

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `module` | string | ✅ | Python 模块路径，从 `adapters/` 根开始解析 |
| `factory` | string | ✅ | 模块内的可调用名（函数或类名），调用时无参数 |

`factory` 调用约定：

- 调用时不传任何位置参数
- 返回一个对象实例
- 这个对象必须满足 manifest 中 `capabilities.provides` 列出的所有端口
- 同一进程内可能被调用多次，每次产生新实例（装配器按需实例化）

V1 简化：V1 不支持带参数的 `factory`。如果模块需要配置，配置通过 `[config]` 的字段传递，装配器在实例化后调用 `instance.configure(config_dict)`。V1 之后才考虑参数化 factory。

### `[capabilities]` —— 能力声明

| 字段 | 类型 | 必填 | 含义 |
|---|---|---|---|
| `provides` | string[] | ✅ | 模块实现了哪些端口。V1 仅允许 `MemoryPort` 或 `ToolPort`，见下方"保留端口"小节 |
| `requires` | string[] | ✅（可空） | 模块依赖哪些端口。用户选择本模块时，这些端口必须有至少一个模块提供 |
| `conflicts` | string[] | ✅（可空） | 与本模块冲突的其他模块 ID。不可同选 |
| `enhances` | string[] | ✅（可空） | 与本模块协同的其他模块 ID。V1 仅作为提示，不强制 |

`requires` 与 `conflicts` 在 V1 中的处理：

- **必需检测**：选了 A，要求 A.requires 全部满足。装配器检查这些端口是否有至少一个模块在已选集合里提供。缺失则报错，错误码 `E_REQUIRE_NOT_MET`。
- **冲突检测**：选了 A，检查已选集合中是否有 A.conflicts 中的模块 ID。有则报错，错误码 `E_CONFLICT`。

V1 **不**做完整的传递闭包求解（如"选了 X 必须选 Y，选了 Y 又必须选 Z"），但装配器会重复扫描已选集合直到闭包收敛。这覆盖 80% 的实际情况，剩余 20% 留给 V2。

### 保留端口（V1 不允许 adapter 声明）

V1 保留给 Lancelot 自身实现的端口：

- `ModelPort` —— 由 Lancelot 内部 `src/lancelot/model_default/` 提供
- `ChannelPort` —— 由 Lancelot 内部 `src/lancelot/channel_default/` 提供

如果 manifest 的 `capabilities.provides` 包含 `["ModelPort"]` 或 `["ChannelPort"]`，装配器在 scan 阶段**警告**错误 `E_RESERVED_PORT`（不解析、不影响其他模块）。这条规则保证"loop、model、channel 属于 Lancelot"的边界不被 adapter 越过。

V2 计划：把 model/channel 的"可选 / 可替换"开放给 `adapters/`；届时 `E_RESERVED_PORT` 不再有效。

### `[config]` —— 默认配置 schema

| 字段 | 类型 | 必填 | 含义 |
|---|---|---|---|
| `schema` | table | ✅（可空） | 字段名 → 字段约束的映射；空表表示无配置 |

字段约束形式：

```toml
[config.schema]
max_entries = { type = "int",  default = 1024, required = false }
ttl_seconds = { type = "int",  default = 0,    required = false }
api_key     = { type = "str",  default = "",   required = true  }
```

`type` 枚举（V1）：`str` / `int` / `float` / `bool` / `list[str]`。`required = true` 且 `default` 为空时，装配器在 select 阶段会报错而不是默默用空值。

V1 简化：不支持嵌套表、enum、range 等复杂约束。这些属于"看起来很合理"的需求，先不做。

---

## 完整示例（V1 全部内置 adapter）

### `memory.inmemory`（在 `adapters/memory/inmemory/`）

```toml
[adapter]
id            = "memory.inmemory"
name          = "In-Memory Memory"
version       = "0.1.0"
category      = "memory"
description   = "进程内短期记忆，不持久化。仅用于 V1 演示与测试。"
min_framework = "1.0.0"

[entry]
module  = "memory.inmemory"
factory = "create_memory"

[capabilities]
provides = ["MemoryPort"]
requires = []
conflicts = []
enhances = []

[config]
schema = { max_entries = { type = "int", default = 1024, required = false } }
```

### `tools.echo`（在 `adapters/tools/echo/`）

```toml
[adapter]
id            = "tools.echo"
name          = "Echo Tool"
version       = "0.1.0"
category      = "tools"
description   = "把传入的参数原样返回。最简单的工具实现，用于演示 ToolPort。"
min_framework = "1.0.0"

[entry]
module  = "tools.echo"
factory = "create_tool"

[capabilities]
provides = ["ToolPort"]
requires = []
conflicts = []
enhances = []

[config]
schema = {}
```

---

## scan 阶段如何使用

```
对每个 adapters/<dir>/：
    1. 读 adapters/<dir>/MANIFEST.toml
    2. 校验顶层表头是 [adapter]，否则报 E_KIND_MISMATCH
    3. 用 schema 校验所有必填字段存在、类型正确、ID 与目录布局一致
    4. 校验 provides 不含保留端口（ModelPort、ChannelPort），
         否则报 E_RESERVED_PORT
    5. 校验通过 → 加入 Registry
    6. 校验失败 → 报错，停在当前模块，继续扫下一个
```

V1 **不扫** `plugins/` 目录（V1 不实现 plugin loader）。

**关键纪律**：scan 不 `import` 任何模块代码，不调用 factory，不读 `__init__.py`。它只读 MANIFEST.toml。`__init__.py` 的存在仅用于校验（生成阶段才被 import）。

---

## 错误码

| 码 | 含义 |
|---|---|
| `E_MANIFEST_MISSING` | 目录下找不到 MANIFEST.toml |
| `E_MANIFEST_PARSE` | TOML 语法错（tomllib 抛错） |
| `E_MANIFEST_INVALID` | schema 校验失败（缺字段、类型错、ID 与目录不一致等） |
| `E_KIND_MISMATCH` | 顶层表头不是 `[adapter]`（V1 仅接受此一种） |
| `E_RESERVED_PORT` | `capabilities.provides` 包含保留端口（`ModelPort` 或 `ChannelPort`） |
| `E_DUPLICATE_ID` | 同一 ID 在多处出现 |
| `E_CATEGORY_MISMATCH` | `category` 不在 V1 枚举（`memory` / `tools`）内，或与目录前缀不一致 |

错误信息必须包含：模块路径、字段名、期望类型/值、实际收到的内容。原始 `tomllib.TOMLDecodeError` 等异常**禁止**穿透到用户层。

---

## 演化规则

- **向后兼容**：只能新增字段、不能删除字段、不能改字段类型。新增字段必须有默认值或 `required = false`。
- **主版本号变更**：当字段语义变化或表重命名时，模块 `version` 必须升 MAJOR。装配器读取 manifest 时记录 module version，便于回溯。
- **Manifest 协议自身版本**：当本协议表结构变化时（本文件被不向后兼容地修改），由 Lancelot 自身的 manifest schema version 表达（V1 暂用"无版本号"简化策略——本文件改一次，硬重启 V1）。

---

## 与其他文档的关系

- 端口契约见 [`03-端口契约.md`](03-端口契约.md)。`capabilities.provides` 中的端口名在那里定义。
- 装配器怎么用这些字段做必需/冲突检测见 [`04-装配器协议.md`](04-装配器协议.md)。
- 怎么验证模块"确实满足"它声明的端口见 [`05-合规性测试规范.md`](05-合规性测试规范.md)。
- 完整 adapter 作者视角的工作流见 [`06-插件开发指南.md`](06-插件开发指南.md)。