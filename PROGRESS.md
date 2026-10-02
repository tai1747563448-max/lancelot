# Lancelot V1 实施进度看板

> 最近更新：2026-10-02
> 当前 commit：见 `git log`；最新 push：`tai1747563448-max/lancelot@main`
> 读者：所有 V1 参与者

---

## 一句话状态

V1 **端到端完成**：8 条成功判据全部活体验证，30 个 compliance 测试全绿，
P1 工程加固完成，重构收敛完毕——高内聚低耦合无冗余。

---

## V1 8 条成功判据状态

| # | 判据 | 状态 | 验证命令 |
|---|---|---|---|
| 1 | `lancelot scan` 能列出内置 adapter | ✅ | `lancelot scan` → 3 adapters, 3 OK, 0 warnings |
| 2 | bare Lancelot 能直接 `lancelot run` | ✅ | `lancelot run <<<ping` → `[mock] ping` |
| 3 | `compose --use memory.inmemory --use tools.echo --name myapp` 生成可独立运行 CLI | ✅ | `compose` → 15 文件写入 `generated/myapp/` |
| 4 | 启动生成 CLI 能跑一次 agent 循环 | ✅ | `python generated/myapp/app/main.py` → `[mock] hello` |
| 5 | 替换内置记忆为另一个 mock 实现，组合代码不动 | ✅ | `compose --use memory.lru ...` 生成可跑产物；composition.py 引用 `--use` 不引用具体 adapter |
| 6 | `pytest tests/compliance` 全部通过 | ✅ | 30 passed (18 MemoryPort + 12 ToolPort) |
| 7 | 删除 `generated/` 后重生成完整 | ✅ | `rm -rf generated && compose` → 重跑成功 |
| 8 | 生成物拷到无 Lancelot 机器能直接跑 | ✅ | 直接 `python generated/myapp/app/main.py`，无 PYTHONPATH 设置 |

**进度**：8/8 完成。

---

## V1 文件清单（commit `d751e16` + 重构后）

### application 装配器（7 模块 + 5 模板）

| 文件 | 行数 | 作用 |
|---|---|---|
| `src/lancelot/application/state.py` | 49 | AssemblerState（adapters_root/output_root/plugins_root-V2预留/registry/selection/name） |
| `src/lancelot/application/registry.py` | 82 | register / find_by_id / find_by_capability / all / size |
| `src/lancelot/application/scanner.py` | ~370 | scan 动作 + `_warn()` helper（5 处重复变 1 处） |
| `src/lancelot/application/selector.py` | 121 | select 动作（require/conflict/dup 检测） |
| `src/lancelot/application/generator.py` | ~290 | generate 动作 + `_render_one()` / `_write_text()` / `_copytree()` helpers |
| `src/lancelot/application/launcher.py` | 65 | launch 动作（subprocess.run fork-exec） |
| `src/lancelot/application/runner.py` | 78 | run 动作（bare 模式不写文件） |
| `templates/composition.py.j2` | 90 | 生成物组合代码（adapter 实例化 + loop 装配） |
| `templates/main.py.j2` | 30 | 生成物入口 |
| `templates/config.yaml.j2` | 28 | 固化选择 + defaults |
| `templates/README.md.j2` | 31 | 生成物自带 README |
| `templates/pyproject.toml.j2` | 12 | 生成物依赖声明 |

### 上层基础（6 模块）

| 文件 | 行数 | 作用 |
|---|---|---|
| `src/lancelot/errors.py` | 130 | 22 个错误类（按家族：Config / PortAddress / Adapters / Generate / Runtime）；`DuplicateIdError` 改为 `RegistryError` 子类 |
| `src/lancelot/domain/{types.py,__init__.py}` | 170+26 | 8 个 dataclass |
| `src/lancelot/ports/{memory,tool,model,channel}.py + __init__.py` | 23+32+27+33+19 | 4 个 Protocol |
| `src/lancelot/model_default/{mock.py,__init__.py}` | 38+4 | MockModel + `[mock] echo` |
| `src/lancelot/channel_default/{stdio.py,__init__.py}` | 76+4 | StdioChannel + stdin prompt + EOF→None |
| `src/lancelot/loop/{single_loop.py,__init__.py}` | 158+4 | SingleLoop + `import sys` 移到模块顶 |

### CLI 入口（3 文件）

| 文件 | 行数 | 作用 |
|---|---|---|
| `src/lancelot/__init__.py` | 31 | 包 docstring + `__version__ = "1.0.0"` |
| `src/lancelot/cli.py` | 290 | argparse（`--adapters-root` 全局化） + `_EXIT_CODE_TABLE` 表驱动分发 + `_DISPATCH` 字典 |
| `src/lancelot/__main__.py` | 17 | `python -m lancelot` 入口 |

### 内置 adapter（3 个）

| 目录 | 作用 |
|---|---|
| `adapters/memory/inmemory/` | FIFO 淘汰，max_entries default 1024 |
| `adapters/memory/lru/` | **新增**——LRU 淘汰（get/put 都刷新顺序），max_entries default 512 |
| `adapters/tools/echo/` | 回显工具（dict-shape 返回） |

### 测试（30 tests）

| 文件 | 行数 | 覆盖 |
|---|---|---|
| `tests/compliance/test_memory_port_compliance.py` | ~150 | 9 cases × 2 adapters（inmemory + lru）= 18 tests |
| `tests/compliance/test_tool_port_compliance.py` | ~150 | 12 cases × 1 adapter（echo）= 12 tests |

---

## 重构总结（高内聚低耦合无冗余）

### A. 错误家族统一（**核心改动**）

所有 application/* 模块散落的本地异常（`AdapterNotFoundError` /
`DuplicateIdInSelectionError` / `GeneratedDirMissingError` /
`MainPyMissingError` / `OutputDirExistsError` / `CopyFailedError` /
`TemplateRenderFailedError`）**统一迁移到 `errors.py`**。

- **改前**：每个模块在文件顶部定义 1-3 个异常类；cli.py 需要从 3 个不同的 application/* 模块分别 import。
- **改后**：所有异常集中一处，cli.py 一个 `from lancelot.errors import (...)` 搞定。
- 副作用：`DuplicateIdError` 父类从 `ManifestError` 改为 `RegistryError`（语义更准确：它是 Registry 协议违例，不是 manifest 字段错）；scanner.py 的字符串匹配 `if "already registered" in str(e)` 因此被消除——直接 `except DuplicateIdError`。

### B. cli.py 表驱动分发

| 改前 | 改后 |
|---|---|
| `if args.command == "scan": ...` × 4 个 `if` | `_DISPATCH = {"scan": _cmd_scan, ...}` 字典查找 |
| `_exit_code_for` 4 个 isinstance 判断 | `_EXIT_CODE_TABLE` 表 + 单一 walk |

### C. scanner.py warning helper

`report.warnings.append(ScanWarning(code=..., message=..., adapter_dir=...))` 出现 5 次。提取 `_warn(report, code, msg, adapter_dir)` 后变成一行调用。

### D. generator.py helpers

| helper | 消除的重复 |
|---|---|
| `_copytree(src, dst)` | 2 处 `shutil.copytree` 都加 `ignore=shutil.ignore_patterns("__pycache__", "*.pyc")` |
| `_render_one(env, tpl_name, out_path, ctx, report, report_rel)` | 5 处"加载模板 → 渲染 → 写文件" try/except 合并 |
| `_write_text(out_path, content, report, report_rel)` | 6 处 `write_text` + `mkdir(parents=True)` + `report.written.append` 合并 |

### E. 死代码清理

- `runner.py`：移除未使用 `import sys`
- `single_loop.py`：`import sys` 从函数体内移到模块顶
- `scanner.py`：移除 `try/except RegistryError` 死防御（registry.register 失败只可能是 DuplicateIdError）

### F. CLI 参数全局化

`--adapters-root` 从 scan / compose 子命令移到顶层 parser。所有 4 个子命令统一接受（run/launch 不读但接受）。

### G. 其他

- `pyproject.toml` 从 0 字节补全为 `[project]` + `[project.scripts]` + `[project.optional-dependencies]` + `[tool.pytest.ini_options]`（`pythonpath = ["src"]` 让 pytest 不依赖外部 `PYTHONPATH=src`）
- generator 复制时忽略 `__pycache__` / `*.pyc`（避免污染生成物）
- `state.plugins_root` 字段加注释"V2 预留"（避免后人误删）
- `DuplicateIdError` 父类改为 `RegistryError`——scanner 不再需要字符串匹配

---

## 关键不变量（避免下次接活踩坑）

- **生成物不持有 Lancelot source tree 的引用**：所有 runtime import 必须用包内相对路径（`from .X` / `from ..X`），绝不写 `from lancelot.X import Y`。Generator 用 `shutil.copytree` 物理复制，不留符号链接。
- **scan 不执行 adapter 代码**：scanner 只读 `MANIFEST.toml`，不 `import __init__.py`。adapter 实现里的代码在 generate 阶段才被 import。
- **adapter 用 duck-typing**：adapter 不直接 import Lancelot 领域类型（`MemoryEntry` / `ToolResult` 等），用 `Any` + duck typing。
- **保留端口不可越**：`ModelPort` / `ChannelPort` 由 Lancelot 内部实现，adapter manifest `provides = ["ModelPort"]` 触发 `E_RESERVED_PORT` 警告。
- **错误家族统一**：所有 Lancelot 异常继承 `LancelotError`。**所有错误类都在 `errors.py`**——不在 application/* 模块里再散落定义。cli.py 的 `_EXIT_CODE_TABLE` 是异常 → 退出码的单一映射点。
- **退出码集中映射**：launch 家族（5）必须先于 generate 家族（4）判断，因为前者继承后者；这条不变量体现在 `_EXIT_CODE_TABLE` 的元组顺序里。
- **scanner 不可能产生 duplicate id**（id = path，每个 path 只产生一个 adapter 元数据），但 `Registry.register` 仍然抛出 `DuplicateIdError`（继承 `RegistryError`）作为防御——保留这条不变量以备 scanner 演化。

---

## 端到端 smoke 脚本（参考）

```bash
# 前置：仓库根下（pyproject.toml 自带 pythonpath = ["src"]，无需 PYTHONPATH=src）

# 成功判据 1
lancelot scan
# 预期：3 adapters, 3 OK, 0 warnings

# 成功判据 3 / 7 / 8
rm -rf generated  # 删旧生成物
lancelot compose --use memory.inmemory --use tools.echo --name myapp
# 预期：15 文件写入 generated/myapp/
python generated/myapp/app/main.py <<< "hello world"
# 预期：
#   > [mock] hello world
#   >

# 成功判据 4 / 走装配器
lancelot launch myapp <<< "hi"
# 预期：
#   > [mock] hi
#   >

# 成功判据 2（bare 模式，无 adapter）
printf "ping\n" | lancelot run
# 预期：
#   > [mock] ping
#   >

# 成功判据 5（换 adapter 不动组合代码）
lancelot compose --use memory.lru --use tools.echo --name myapp
# 预期：同 15 文件 + adapters/memory/lru/ 被复制
python generated/myapp/app/main.py <<< "hello world"
# 预期：同 [mock] hello world 行为

# 成功判据 6
pytest tests/compliance/
# 预期：30 passed in 0.07s
```

---

## V1 之后的演进候选

V1 是端到端骨架。下一步候选（按优先级，未排期）：

- **V1.1 真模型支持**：`model_default/openai.py` / `anthropic.py`；保留端口放开，adapter 可声明 ModelPort（先实现 Lancelot 内部真模型）。
- **V1.2 plugin loader**：state.plugins_root 已经有，差一个 loader + 选择算法。
- **错误信息国际化**：当前中英混合，V2 起明确单一语言。
- **`examples/run_smoke.sh`**：一键跑完 8 条判据的演示脚本（V1 没做，每个开发者自己拼命令）。
