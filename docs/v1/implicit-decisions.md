# V1 隐式决策清单（Implicit Decisions）

> 版本：v1.0（2026-10-03）
> 读者：所有想真正"理解"V1 而不只是"用"V1 的开发者
> 配套：`docs/08-V1完成报告.md`（讲 V1 是什么）+ 本文件（讲 V1 **为什么**长这样）

---

## 这是什么

Lancelot V1 的代码里有一类决策，**不是从任何用户 prompt 直接翻译过来的**——是我（AI）在实现时根据工程直觉做的选择。如果不读这些位置，下次改代码时容易踩坑；如果读了你不同意，未来推翻重写也很容易。

按"错了会怎样"分三档：

| 档 | 含义 | 该花时间 |
|---|---|---|
| 🔴 红色 | 错了就坏（语义错位 / 不可逆的协议决定 / 隐式安全风险） | **必须读** |
| 🟡 黄色 | 错了下游会变（约定改了别人要跟着改 / deprecation API） | 应该读 |
| 🟢 绿色 | 纯风格 / 排版选择（错了也没人发现） | 可以忽略 |

---

## 🔴 红色：错了就坏

### #1 `loop/single_loop.py:171-193` — `_invoke_tool` 的 duck-typing 顺序

```python
if isinstance(raw, ToolResult): ...   # 第 1 档
if isinstance(raw, dict): ...         # 第 2 档
if hasattr(raw, "content"): ...       # 第 3 档
return ToolResult(..., str(raw))      # 兜底
```

**顺序不可交换**。如果未来想让 adapter **同时**返回 dict 接口和 duck-typed 接口，顺序决定走哪档。

**风险**：未来重构 duck-typed adapter 时容易踩坑——比如返回 dict 但有 `.content` 属性，会被第 2 档先吃掉。

---

### #2 `loop/single_loop.py:161-168` — 工具调用失败的处理哲学

我定的：**捕获异常 → 包成 `is_error=True` ToolResult → 不破坏 loop**

备选：让 `ToolError` 透传 → loop 整个挂掉。

这是 **"fail-soft" vs "fail-loud"** 的取舍。

- 当前选择适合 demo / happy path
- 生产环境你想要"fail-loud"——bug 应该显形，不是被吃掉

---

### #3 `loop/single_loop.py:100-105` — `memory.put` 失败的处理

```python
except Exception as e:
    print(f"[loop] memory.put failed: {e}", file=sys.stderr)
```

**我的假设**：memory 失败不应该阻塞对话。

但这是个**哲学选择**——bug 应该显形还是隐身？如果你的 memory 是商业关键路径（不是 demo），吞掉异常是危险的。

---

### #4 `loop/single_loop.py:108-110` — max_turns 用尽

我定的：抛 `LoopError`
备选：静默 return

---

### #5 `ports/model.py:19-23` — **ModelPort 是同步的**

```python
def generate(self, messages: List[Message]) -> Message:
```

这是 V1 **不能流式输出** 的根因。

- 备选 1：`AsyncIterator[Message]`（async 协议）
- 备选 2：`Iterator[Message]`（sync generator）
- 备选 3：SSE / chunk 协议（协议级）

**不可逆**：流式是协议级改动，要重新设计 loop、channel、CLI 拼装、composition.py 模板。

**这值得你单独思考 5 分钟**——V1 的核心体验差就在这里。

---

### #6 `generator.py:198` — `datetime.utcnow()`

```python
"timestamp": _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
```

`utcnow()` 在 Python 3.12+ **已 deprecated**：

- 3.12 / 3.13：DeprecationWarning
- 3.15：移除

**修复路径**：`datetime.now(timezone.utc)`。
但这会让生成物的时间戳带 `+00:00` 而不是 `Z`——你想保留 `Z` 还是同步改成 `+00:00`？是个**格式决策**。

---

### #7 `generator.py:185` — Jinja2 `StrictUndefined`

```python
undefined=StrictUndefined,  # 漏传上下文立即报错
```

我定的 fail-fast：漏传模板变量立即报错。

备选：默认 `Undefined`（漏传 → 空字符串）。**更宽松但更脆弱**——模板改动时容易静默生成错误内容。

如果未来模板要支持可选字段，这条要放宽。

---

### #8 `selector.py:67` — **空 `--use` 的默认行为**

```python
if not ids:
    ids = [a.id for a in registry.all()]  # 默认选全部
```

我做了一个"便利 fallback"。

**风险场景**：未来 registry 塞了几百个 adapter，开发者漏写 `--use` 时会被自动装一堆东西——这不是便利，是**安全漏洞**。

- 我选了"便利"
- 你可能想："必须显式指定，没有 fallback"

**这个错的话用户体验会非常差**。

---

### #9 `scanner.py:295-301` — `id = path` 强制约束

```python
expected_rel = Path(*aid.split("."))
actual_rel   = adapter_dir.relative_to(adapters_root)
if actual_rel != expected_rel:
    raise ManifestInvalidError(...)
```

manifest.id 必须等于目录路径（`memory.inmemory` ↔ `adapters/memory/inmemory/`）。

**这意味着同一 id 不能在两个 path 注册**——registry.register 的 `DuplicateIdError` 因此是**死防御**。

**不可逆**：未来如果允许 alias / version-suffix（如 `memory.inmemory.v2`），这条要放松。

---

### #10 `errors.py` 整个家族的设计

5 个根家族：

```
LancelotError
├── LancelotConfigError (manifest 解析)
├── LancelotPortAddressError (port / registry)
├── LancelotAdaptersError (select / conflict)
├── GenerateError (compose / launch)
└── LancelotRuntimeError (model / tool / memory / channel / loop)
```

这 5 个家族 ↔ `cli._EXIT_CODE_TABLE` 的 5 个退出码。**整个 cli 错误分发逻辑建立在这个分类上**。

**反思点**：异常分类合理吗？比如：

- `LancelotConfigError` 和 `GenerateError` 都是"装配阶段失败"，为啥分开？
- runtime 错误（model / tool / memory / channel / loop）是不是该再细分？

---

## 🟡 黄色：约定变了下游会变

### #11 `loop/single_loop.py:98` — MemoryEntry 的 key 格式

```python
key=f"msg-{len(session.messages)}"
```

**这意味着同一次 session 内相同内容的两条消息会互相覆盖**（key 是序号不是内容）。

如果你想"按内容去重"或"按时间检索"，这条要改。

---

### #12 `loop/single_loop.py:49-50` — `create_loop` 的 max_turns 校验

```python
if max_turns <= 0:
    raise LoopError(...)
```

V1 没测试覆盖。max_turns=0 想表示"无限制"？这里要改。

---

### #13 `channel_default/stdio.py:19` — prompt `"> "`

用户**真的会看到这个字符串**。CI 测试可能依赖它做字面匹配。
改之前 grep 一下整个仓库。

---

### #14 `channel_default/stdio.py:68` — 行尾处理

```python
return Message(role="user", content=line.rstrip("\n").rstrip("\r"))
```

我两步 strip（先 `\n` 后 `\r`）。

**当前写法在 CRLF 文件 + Windows `printf` 输入时会留下孤立 `\r` 吗？**

更稳健：`.rstrip("\r\n")` 一次调用。

---

### #15 `model_default/mock.py:28` — `PREFIX = "[mock] "`

用户能看到。compliance 测试也依赖它做 substring match。

改 = 改测试 + 改所有"我以为 V1 输出长这样"的认知。

---

### #16 `model_default/mock.py:33-34` — 空 messages 抛 ModelError

我选的"fail-loud"。你想要"返回默认回复（如 `[mock] hello`）"吗？

---

### #17 `generator.py:50-51` — `_RUNTIME_DIRS` / `_RUNTIME_FILES`

```python
_RUNTIME_DIRS  = ("domain", "ports", "loop", "model_default", "channel_default")
_RUNTIME_FILES = ("errors.py",)
```

**cli.py 和 application/ 不复制**——这是"生成物能否升级 Lancelot 自己"的开关。

如果未来想让生成物能 hot-reload Lancelot，application/ 也得复制过去——但那是个新故事。

---

### #18 `generator.py:_copytree` — ignore 列表

```python
ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
```

只忽略了这两个。**未来可能要加**：

- `.git`, `.DS_Store`, `.vscode`, `.idea`
- `*.swp`, `*~`, `Thumbs.db`
- `*.egg-info`, `build/`, `dist/`

---

### #19 `ports/memory.py:28` — `list(limit=100)` 默认

数字我随便挑的。如果接的 LLM 上下文窗口很大，100 不够用；如果你想减少 memory 占用，100 可能太多。

---

### #20 `ports/tool.py:29` — `invoke(**kwargs: object)`

我用 `object`（最宽松）。改 TypedDict = adapter 作者多写代码。

---

### #21 `ports/channel.py:19` — EOF 返回 None

```python
def read(self) -> Optional[Message]:  # None = EOF
```

备选：抛 EOFError，更显式。
当前写法更 Pythonic（iter protocol 风格），但 caller 必须记得查 None。

---

### #22 `domain/types.py:43-57` — Session 可变，Message 冻结

```python
@dataclass                      # 可变
class Session: ...

@dataclass(frozen=True)          # 冻结
class Message: ...
```

规则："对话历史 in-place 累积"。

**反推**：

- 能 `session.messages[0].content = "x"` 吗？**不能**（Message 冻结）
- 能 `session.messages.append(Message(...))` 吗？**能**
- 能 `session.messages.clear()` 吗？**能**

**这是你想要的不变量吗？** 想清楚再继续。

---

### #23 `domain/types.py:79` — `MemoryEntry.timestamp: Optional[float]`

我用 float（支持分数秒）。比较和 hash 时容易踩坑。
如果你不在意 sub-second，int 更安全。

---

### #24 `domain/types.py:118-124` — `Task` 类型 V1 不用

我加的 V2 铺垫。没人 raise，没人构造，V1 没测试覆盖。
V2 接进来时类型签名可能跟代码不一致。

---

### #25 `domain/types.py:131-135` — `Capability.version` 永远 `"1.0.0"`

scanner 在 `_parse_manifest` 里 hard-code 了。
**V1 完全不支持版本管理**——你必须升 V2 才能 declare version mismatch。

---

### #26 `application/state.py:44-45` — `plugins_root` 字段保留

V2 预留。没人用、没人 set、没人读。
可以现在删等 V2 再加（更干净）；也可以保留（更"前瞻"）。

---

### #27 `adapters/memory/lru/__init__.py` — OrderedDict 实现 LRU

```python
self._store.move_to_end(key)         # get 命中 → 移到末尾
self._store.popitem(last=False)      # 满了 → 删头部（最久未用）
```

备选：`dict` + 手动维护 LRU list。更精细但实现复杂。

**性能 vs 复杂度** 我选了前者——Python 3.7+ `dict` 已保证 insertion order，OrderedDict 是轻量包装。

---

### #28 `adapters/memory/lru/__init__.py` — `max_entries` 默认 512

数字我随便挑的（区别于 inmemory 的 1024）。**没性能依据**。
跑 perf 测试发现需要调，这个数字有依据地换。

---

### #29 `adapters/tools/echo/__init__.py:55-58` — 返回 dict 而非 ToolResult

```python
return {"content": json.dumps(...), "is_error": False}
```

echo 返回 dict 形态（loop duck-typing 第 2 档）。
**这条是 V1 重要不变量**——compliance test 里专门有 AST 检查确保 adapter 不 import lancelot。

如果未来放宽 duck-typed 纪律，这个测试要删。

---

### #30 `tests/compliance/test_tool_port_compliance.py` — AST 检查 `from lancelot`

我加了 `test_echo_adapter_does_not_import_lancelot`，**不在原始 8 条判据里**。
是我加的纪律测试。

如果你想允许 adapter import lancelot（更宽松），删这个测试。

---

### #31 `cli.py` — 所有 `--help` 文案

argparse 的 help 字符串都是我自己写的。**用户友好度看你的标准**。
如果要 i18n，文案要全审一遍。

---

## 🟢 绿色：纯风格 / 排版（5 项）

- **引号风格**：双引号
- **f-string**：全用 f-string，不用 `.format()`
- **`from __future__ import annotations`**：每个文件都加
- **`Optional[X]` vs `X | None`**：**不一致**——cli.py 用 `Optional`，generator.py 用 `Path | None`。下次写新代码统一一下。
- **`_RUNTIME_DIRS` 用元组不是 list**：因为不可变；选择随意

---

## 怎么用这份清单

### 现在（V1 已交付，立刻该做的）

1. **先读 🔴 #5（ModelPort 同步）和 #8（空 `--use` fallback）**——它们影响你将来怎么用 Lancelot（流式 vs 同步、默认行为是否安全）。这两条决定的是产品方向。
2. **再扫一遍 🟡 #6（utcnow deprecated）和 #11（MemoryEntry key 格式）**——一个是会 deprecation 的 API，一个是会破坏功能的 key 格式。今天不修明天崩。

### 之后（碰到再读）

3. **剩下的等你将来真碰到再读**——代码就在那儿，跑一下 `path/to/file.py:L50` 就能跳过去。**不要现在花时间读 30 个文件**——你刚已经读了这张表，这就是今天的全部。

### 下次让 AI 写代码时（可复用方法）

下次让 AI 写一块代码前，自己列一张"我假设它会这么决策"的清单。AI 写完后对比——有差异的地方就是你要读的地方。

这是"对 AI 输出做 code review"的实操路径。

---

## 配套文档

- `docs/01-V1范围与边界.md`：V1 设计期定的"做不做"边界（基线）
- `docs/08-V1完成报告.md`：V1 完成后"做到了什么 + 怎么用"（交付）
- `docs/v1/implicit-decisions.md`：**本文**——V1 完成后"哪些决策是我（AI）自主做的"（意图）
