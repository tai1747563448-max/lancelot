# 02 · Manifest 协议

> 状态：草案 v1.0（与 [`01-V1范围与边界.md`](01-V1范围与边界.md) 配套）
> 读者：装配器维护者、插件作者、合规性测试作者
> 范围：定义插件源文件如何用 TOML 描述自己

---

## 这是什么

**Manifest 是一段嵌入在插件源文件旁的 TOML 数据**，由装配器在 **scan 阶段**读取。它声明插件的身份、能力、依赖、入口点。装配器不读取插件的代码来获取这些信息——这条规则保证 "scan 不执行" 的安全边界。

## 这不是什么

- **不是配置文件**：配置是用户输入、由用户/工具改写的运行时参数。Manifest 是插件自己的身份信息，原则上只由插件作者维护。
- **不是代码**：Manifest 不包含可执行逻辑。如果一段逻辑必须存在才能正确组装，把它放进入口函数里。
- **不是二进制元数据**：插件以源文件存在，Manifest 是源文件的一部分，不是编译产物。

---

## 物理布局

每个插件在磁盘上是 **一个目录**，目录内有两个必备文件：

```
plugins/
└── <plugin-id-as-path>/
    ├── MANIFEST.toml           # 必需：插件自描述
    └── __init__.py             # 必需：入口模块（装配器从这里导入）
```

`<plugin-id-as-path>` 是插件 ID 的点号路径形式（如 `memory.inmemory` → `memory/inmemory/`）。这条规则保证"目录即 ID"，物理布局和身份一致。

### V1 真实示例（写入到 `plugins/memory/inmemory/`）

`plugins/memory/inmemory/MANIFEST.toml`：

```toml
# === Lancelot Manifest v1 ===
# 解析器：tomllib（标准库）；写回：tomli_w（仅装配器内部使用）

[plugin]
id            = "memory.inmemory"
name          = "In-Memory Memory"
version       = "0.1.0"
category      = "memory"
description   = "进程内短期记忆，不持久化。仅用于 V1 演示与测试。"
min_framework = "1.0.0"

[entry]
module  = "lancelot_adapters.memory.inmemory"
factory = "create_memory"

[capabilities]
provides = ["MemoryPort"]
requires = []
conflicts = []
enhances = []

[config]
schema = { max_entries = { type = "int", default = 1024, required = false } }
```

`plugins/memory/inmemory/__init__.py`：

```python
"""memory.inmemory —— 满足 MemoryPort 的最小实现。"""

from .adapter import create_memory

__all__ = ["create_memory"]
```

---

## TOML Schema（v1）

Manifest 顶层有 4 个 table：`[plugin]`、`[entry]`、`[capabilities]`、`[config]`。

### `[plugin]` —— 身份

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `id` | string | ✅ | 形如 `<category>.<name>`，全局唯一，正则 `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$` |
| `name` | string | ✅ | 人类可读，<= 64 字符 |
| `version` | string | ✅ | SemVer `MAJOR.MINOR.PATCH`，可选预发布标签 |
| `category` | string | ✅ | 枚举：`memory` / `tools` / `model` / `channel` / `agent` |
| `description` | string | ✅ | 人类可读，<= 256 字符 |
| `min_framework` | string | ✅ | Lancelot 主版本约束（如 `"1.0.0"`，V1 简化为字符串等值匹配） |

`id` 与目录布局强绑定：插件 ID 是 `memory.inmemory`，物理目录必须是 `plugins/memory/inmemory/`。这条规则让"忘记改 Manifest 但改了目录"这种漂移立即可见。

### `[entry]` —— 入口点

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `module` | string | ✅ | Python 模块路径，从装配器的导入根开始解析 |
| `factory` | string | ✅ | 模块内的可调用名（函数或类名），调用时无参数 |

`factory` 调用约定：

- 调用时不传任何位置参数
- 返回一个对象实例
- 这个对象必须满足 Manifest 中 `capabilities.provides` 列出的所有端口
- 同一进程内可能被调用多次，每次产生新实例（装配器按需实例化）

V1 简化：V1 不支持带参数的 `factory`。如果插件需要配置，配置通过 `[config]` 的字段传递，装配器在实例化后调用 `instance.configure(config_dict)`。V1 之后才考虑参数化 factory。

### `[capabilities]` —— 能力声明

| 字段 | 类型 | 必填 | 含义 |
|---|---|---|---|
| `provides` | string[] | ✅ | 插件实现了哪些端口。装配器据此建立"插件 ↔ 端口"映射 |
| `requires` | string[] | ✅（可空） | 插件依赖哪些端口。用户选择本插件时，这些端口必须有插件提供 |
| `conflicts` | string[] | ✅（可空） | 与本插件冲突的其他插件 ID。不可同选 |
| `enhances` | string[] | ✅（可空） | 与本插件协同的其他插件 ID。V1 仅作为提示，不强制 |

`requires` 与 `conflicts` 在 V1 中的处理：

- **必需检测**：选了 A，要求 A.requires 全部满足。装配器检查这些端口是否有至少一个插件在已选集合里提供。缺失则报错，错误码 `E_REQUIRE_NOT_MET`。
- **冲突检测**：选了 A，检查已选集合中是否有 A.conflicts 中的插件。有则报错，错误码 `E_CONFLICT`。

V1 **不**做完整的传递闭包求解（如"选了 X 必须选 Y，选了 Y 又必须选 Z"），但装配器会重复扫描已选集合直到闭包收敛。这覆盖 80% 的实际情况，剩余 20% 留给 V2。

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

## 完整示例（V1 全部内置插件）

### `model.mock`

```toml
[plugin]
id            = "model.mock"
name          = "Mock Model"
version       = "0.1.0"
category      = "model"
description   = "回显输入的伪模型。V1 唯一模型实现，用于演示与测试。"
min_framework = "1.0.0"

[entry]
module  = "lancelot_adapters.model.mock"
factory = "create_model"

[capabilities]
provides = ["ModelPort"]
requires = []
conflicts = []
enhances = []

[config]
schema = { response_prefix = { type = "str", default = "[mock] ", required = false } }
```

### `tools.echo`

```toml
[plugin]
id            = "tools.echo"
name          = "Echo Tool"
version       = "0.1.0"
category      = "tools"
description   = "把传入的参数原样返回。最简单的工具实现，用于演示 ToolPort。"
min_framework = "1.0.0"

[entry]
module  = "lancelot_adapters.tools.echo"
factory = "create_tool"

[capabilities]
provides = ["ToolPort"]
requires = []
conflicts = []
enhances = []

[config]
schema = {}
```

### `channel.cli`

```toml
[plugin]
id            = "channel.cli"
name          = "CLI Channel"
version       = "0.1.0"
category      = "channel"
description   = "从 stdin 读输入、向 stdout 写输出。最简 channel。"
min_framework = "1.0.0"

[entry]
module  = "lancelot_adapters.channel.cli"
factory = "create_channel"

[capabilities]
provides = ["ChannelPort"]
requires = []
conflicts = []
enhances = []

[config]
schema = { prompt = { type = "str", default = "> ", required = false } }
```

---

## scan 阶段如何使用

```
对每个已知插件路径 plugins/<dir>/：
    1. 读 plugins/<dir>/MANIFEST.toml，纯文本解析（tomllib）
    2. 用 schema 校验所有必填字段存在、类型正确、ID 与目录布局一致
    3. 校验通过 → 加入 Registry
    4. 校验失败 → 报错 E_MANIFEST_INVALID，停在当前插件，继续扫下一个
```

**关键纪律**：scan 不 `import` 任何插件代码，不调用 factory，不读 `__init__.py`。它只读 MANIFEST.toml。`__init__.py` 的存在仅用于校验（生成阶段才被 import）。

---

## 错误码

| 码 | 含义 |
|---|---|
| `E_MANIFEST_MISSING` | 目录下找不到 MANIFEST.toml |
| `E_MANIFEST_PARSE` | TOML 语法错（tomllib 抛错） |
| `E_MANIFEST_INVALID` | schema 校验失败（缺字段、类型错、ID 与目录不一致等） |
| `E_DUPLICATE_ID` | 同一 ID 在多处出现 |
| `E_CATEGORY_MISMATCH` | `category` 不在枚举内，或与目录前缀不一致 |

错误信息必须包含：插件路径、字段名、期望类型/值、实际收到的内容。原始 `tomllib.TOMLDecodeError` 等异常**禁止**穿透到用户层。

---

## 演化规则

- **向后兼容**：只能新增字段、不能删除字段、不能改字段类型。新增字段必须有默认值或 `required = false`。
- **主版本号变更**：当字段语义变化或表重命名时，plugin.version 必须升 MAJOR。装配器读取 manifest 时记录 plugin.version，便于回溯。
- **Manifest 协议自身版本**：当本协议表结构变化时（本文件被不向后兼容地修改），由 Lancelot 自身的 manifest schema version 表达（V1 暂用"无版本号"简化策略——本文件改一次，硬重启 V1）。

---

## 与其他文档的关系

- 端口契约见 [`03-端口契约.md`](03-端口契约.md)。`capabilities.provides` 中的端口名在那里定义。
- 装配器怎么用这些字段做必需/冲突检测见 [`04-装配器协议.md`](04-装配器协议.md)。
- 怎么验证插件"确实满足"它声明的端口见 [`05-合规性测试规范.md`](05-合规性测试规范.md)。
- 完整插件作者视角的工作流见 [`06-插件开发指南.md`](06-插件开发指南.md)。
