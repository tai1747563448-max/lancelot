# Lancelot 装配器实现 Handoff

> 本文档给下一个会话/agent 看——目的是让"零上下文"也能接活实现装配器。

## 项目是什么

**Lancelot** = 元框架（meta-framework），用来造 agent 框架的工具。它**不是** agent 框架本身，是"组装说明书 + 组装器"。

- 仓库：`E:/desktop/How_to_build_a_agent/Lancelot/`
- 远端：`https://github.com/tai1747563448-max/lancelot`，分支 `main`，push 必须用 `:443` 端口绕开 ghfast.top
- 状态：8 份基线文档已写完并 push、占位骨架已建、本轮要实现 **application 装配器**

## V1 锁定决策（实现必须遵守）

1. Python >= 3.11 + TOML Manifest + CLI 形态（stdin/stdout）
2. **loop/model/channel 都属于 Lancelot 内部**（不在 adapter 范畴），由 `src/lancelot/{loop,model_default,channel_default}/` 实现
3. **adapter 只有两类**：memory + tools
4. V1 内置 2 个 adapter：`memory.inmemory`、`tools.echo`
5. V1 不实现 plugin loader；`plugins/` V1 空
6. "reserved port"：`ModelPort`/`ChannelPort` 禁止 manifest 声明（违反触发 `E_RESERVED_PORT` 警告）
7. V1 端口清单：`MemoryPort`（adapter 满足）+ `ToolPort`（adapter 满足）+ `ModelPort`（保留）+ `ChannelPort`（保留）+ `Registry`
8. 8 条成功判据是 V1 验收线（详见 `docs/01-V1范围与边界.md` §"成功判据"）

## 物理布局（已建占位）

```
Lancelot/
├── src/lancelot/                  ← Python 包（Lancelot 库）
│   ├── __init__.py / __main__.py / cli.py / errors.py
│   ├── domain/types.py            ← Message / Session / MemoryEntry / ToolCall / ToolResult / Task / Capability / Adapter
│   ├── ports/{memory,tool,model,channel}.py  ← Protocol 定义
│   ├── loop/single_loop.py        ← Lancelot 唯一 agent loop
│   ├── model_default/mock.py      ← 默认 mock model
│   ├── channel_default/stdio.py   ← 默认 stdio channel
│   └── application/               ← **本次要实现的装配器**
│       ├── state.py               ← AssemblerState（全局状态）
│       ├── registry.py            ← Registry（adapter 元数据表）
│       ├── scanner.py             ← scan 动作
│       ├── selector.py            ← select 动作（require/conflict 检测）
│       ├── generator.py           ← generate 动作（Jinja2 + shutil 复制）
│       ├── launcher.py            ← launch 动作（fork-exec 子进程）
│       ├── runner.py              ← run 动作（bare 模式，不生成文件）
│       └── templates/             ← Jinja2 模板
├── adapters/                      ← **待建占位**
│   ├── memory/inmemory/
│   └── tools/echo/
├── tests/{unit,compliance}/       ← 占位已建，内容空
├── docs/                          ← 8 份基线文档
├── generated/                     ← 默认生成目录
├── pyproject.toml                 ← 占位空，待填
└── .gitignore / README.md
```

## 关键文档（实现前必读）

- **`docs/04-装配器协议.md`** ← **本次实现以此文档为契约**
- `docs/01-V1范围与边界.md` - V1 基线 + 8 条成功判据
- `docs/02-Manifest协议.md` - adapter 怎么描述自己（scan 时读这个）
- `docs/03-端口契约.md` - 4 个端口 + 领域类型 + 错误体系（实现 domain/ports/loop/model/channel 时必读）
- `docs/05-合规性测试规范.md` - compliance 测试规范（V1 仅 2 套：MemoryPort、ToolPort）
- `docs/06-插件开发指南.md` - adapter 作者视角（指导 2 个内置 adapter 怎么写）
- `docs/07-生成物结构.md` - generated/ 目录布局（generator.py 输出的形态）

## 依赖方向（hexagonal 架构）

```
cli.py / __main__.py        ← 用户入口（driving）
   ↓
application/                ← 装配器业务
   ↓
ports/ + loop/ + model_default/ + channel_default/
   ↓
domain/ + errors.py         ← 最内，零依赖
```

**严格单向**：domain → ports → Lancelot 内部实现 → application → cli。**反过来不允许**。

## 实现顺序建议（自底向上）

1. `errors.py` + `domain/types.py`（零依赖基础）
2. `ports/{memory,tool,model,channel}.py`（仅 Protocol 定义）
3. `loop/single_loop.py` + `model_default/mock.py` + `channel_default/stdio.py`（Lancelot 内部三件套）
4. `application/state.py` + `registry.py`（装配器状态）
5. `application/scanner.py`（先跑通，能列出 V1 内置 2 个 adapter）
6. `application/selector.py`（require/conflict 检测）
7. `application/runner.py`（**先跑通 bare 模式**，不写文件就能跑对话 —— 成功判据 2）
8. `application/generator.py` + `templates/`（生成 generated/）
9. `application/launcher.py`（fork-exec 启动生成物）
10. `cli.py` + `__main__.py`（串起来：lancelot scan/run/compose/launch）
11. `adapters/memory/inmemory/` + `adapters/tools/echo/`（2 个内置 adapter + manifest）
12. `tests/compliance/test_memory_port_compliance.py` + `test_tool_port_compliance.py`
13. 端到端跑 8 条成功判据

## 关键纪律（违反任意一条 V1 失败）

- **scan 不执行任何 adapter 代码**：只读 `MANIFEST.toml`，不 import `__init__.py`
- **generate 复制而非引用**：把 `src/lancelot/` 子集复制到 `generated/<name>/lancelot_runtime/`
- **生成物独立性**：`generated/<name>/` 不持有 Lancelot 装配器引用，拷到无 Lancelot 机器能直接跑（成功判据 8）
- **错误家族统一**：所有 Lancelot 异常继承 `LancelotError`，裸 `Exception` 不穿透到用户层
- **保留端口不可越**：`ModelPort`/`ChannelPort` 不可由 adapter 实现
- **`run` 不写文件**：bare 模式只在内存里跑，不留磁盘痕迹

## 环境与依赖

- Python >= 3.11（用 `tomllib`、`Self`、`typing.Protocol`）
- V1 第三方依赖：仅 `tomli_w`（写 TOML；3.11+ 可省）、`pyyaml`（读 config.yaml）、`jinja2`（generate 模板）
- 其它全 stdlib：`pathlib`、`shutil`、`subprocess`、`dataclasses`、`argparse`
- pytest 跑测试

## 当前 Git 状态

- `main` 分支，9 个 commit
- 远端已 push 到 `tai1747563448-max/lancelot`
- 最新 commit：placeholder 结构（`d5b9c38`）
- 工作区干净（placeholder 已 commit）

## 跨会话上下文（agent 自己的记忆）

- 用户语言：中文，技术词与文件路径用英文
- 用户偏好：一次只说一条主线，没说的结尾简提
- Lancelot 与 `AgentFramework` 是不同项目（不要互相引用代码/SDK）
- `office-github` MCP 可用（用户已配置 PAT）
- push 用 `https://github.com:443/...` 端口绕开 ghfast.top
