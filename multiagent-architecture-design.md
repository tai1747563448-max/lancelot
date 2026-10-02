# Multi-Agent 架构设计：从静态组合到自演化

> 状态：设计文档 v1
> 范围：从认识论基础到最小可行代码骨架
> 核心思想：**没有先验的方法，只有实践后的方法**

---

## 目录

1. [核心洞见](#一核心洞见)
2. [认识论基础：命题 vs 问题](#二认识论基础命题-vs-问题)
3. [架构决策树](#三架构决策树)
4. [五个必做对的设计决策](#四五个必做对的设计决策)
5. [起步架构](#五起步架构)
6. [从静态库到自演化](#六从静态库到自演化)
7. [库演化协议](#七库演化协议)
8. [三层评估系统](#八三层评估系统)
9. [元验证：评估系统的评估](#九元验证评估系统的评估)
10. [最小可行循环](#十最小可行循环)
11. [附录：代码骨架](#附录代码骨架)
12. [参考文献与真实先例](#参考文献与真实先例)

---

## 一、核心洞见

我们推导出一个贯穿全文的核心原则：

> **不存在先验正确的 agent 库 / pattern 库 / 分类法。任何预设都是用人类认知边界去框定 LLM 的认知边界。**
>
> 解法不是"设计完美的库"，而是**让库在反馈中演化** —— 类似生物进化：变异不指定，选择有方向。

这条原则的多重含义：

| 层次 | 传统思路 | 自演化思路 |
|---|---|---|
| 架构选择 | 人类预先选好 | LLM 在受限选项中选 |
| Agent 设计 | 人类手工策展 | 库从使用中长出来 |
| 问题分类 | 人类定义分类法 | 分类从结果聚类中涌现 |
| 评估指标 | 人类设计 | 多目标互相对抗，共同演化 |

整个架构是一个**多层反馈系统**，每一层都用同样的原则 —— **没有先验，只有反馈**。

---

## 二、认识论基础：命题 vs 问题

**最高层的分类不是按任务规模，而是按认识论状态。**

### 两种任务的本质区别

| 维度 | 启发式命题（Heuristic Proposition） | 复杂式问题（Complex Problem） |
|---|---|---|
| 结果是否已知 | **未知**（可能证明不存在） | **已知存在** |
| 路径是否已知 | 未知 | 未知 |
| 思维模式 | 发散 | 收敛 |
| 典型失败 | 早收敛 / 局部最优 | 死循环 / 资源耗尽 |
| 评估方式 | 自洽性 + 反例 | 端到端通过 |
| 匹配架构 | Blackboard / 辩论 | Supervisor + 子 agent |
| 状态归属 | 共享黑板 | 私有 session + 显式消息 |

### 为什么这个二分法重要

启发式命题和复杂式问题**不能用同一种架构**：

- 命题用 Supervisor 会被 Supervisor 的"目标导向"压死 —— 因为目标本身就不明确
- 问题用 Blackboard 会陷入无限发散 —— 因为收敛条件已知却被忽略

### 第三类：持续陪伴式（我们漏掉的）

除了命题/问题，还有一类**长生命周期**任务，既不发散也不收敛，而是**事件驱动 + 状态机**：

| 维度 | 与前两类的差异 |
|---|---|
| 时间尺度 | 分钟到天，跨越无数轮交互 |
| 状态归属 | 必须有持久化记忆层 |
| 核心难点 | 状态一致性 + 时间整合 |
| 架构 | Event bus + 持久化 session + 周期整合 |

不能用 Blackboard 让一群 agent 自由碰撞 —— 那会让用户记忆被反复改写。

---

## 三、架构决策树

```
任务是什么？
│
├── 结果与路径都未知（命题）
│   └── Blackboard + 结构化中间表示 + 多样化 soul + 魔鬼代言人 + 显式收敛
│
├── 结果已知、路径未知（问题）
│   ├── 任务可拆解为有限步
│   │   └── Supervisor + 子 agent 池 + 总调度者（仅看进度 + 预算 + 升级）
│   │
│   └── 任务步骤爆炸 / 长生命周期
│       └── 事件驱动 + 持久化 session + 周期性反思（REM-like 整合）
│
└── 高频、路径短、确定性高
    └── 单 agent + 工具就够了，别上多 agent
```

### 判断"该不该拆 agent"的三问

只有三个都 yes 才值得拆：

1. 它有独立的上下文/记忆吗？
2. 它需要独立的失败处理吗？
3. 它需要被独立观察/评测吗？

---

## 四、五个必做对的设计决策

不论选哪种拓扑，这五个决定决定系统是否能用：

### 1. 状态归属
- **共享**：协作直观，但并发写要锁，调试容易"为什么这个字段变了"
- **私有**：解耦干净，但跨 agent 传结构要走显式消息

**推荐**：私有 session + 显式消息 + 必要时定义良好的共享"黑板对象"。

### 2. 通信契约
- **函数调用**：紧耦合
- **消息队列**：松耦合但要序列化
- **结构化事件流**：天然支持可观测性和回放

**推荐**：**结构化事件流 + 类型化消息**。

### 3. 故障边界
- 必须有 cancel token / CancellationToken 沿链路传播
- 一个慢 agent 会拖死整条链
- 必须支持"局部失败不影响整体"

### 4. 可观测性
- 每一步的 input/output、工具调用、token、耗时必须可追溯
- 没有 trace 等于黑盒，多 agent 的"看起来在工作"是最危险的故障

### 5. 资源隔离
- 工具、MCP server、文件句柄该不该共享？
- 共享：方便，但一个 agent 搞坏状态会污染所有人
- 隔离：安全，但跨 agent 协作付出序列化代价

---

## 五、起步架构

```
Supervisor (orchestrator)
   ├─ Planner          （拆任务、出子目标）
   ├─ Worker Pool      （实际执行，可多个实例）
   │    ├─ Researcher
   │    ├─ Coder
   │    └─ Reviewer
   └─ Reflector        （检查 worker 输出，决定重做/继续/汇总）
```

### 为什么是这套

- **Planner** 把任务拆清楚 → 责任清晰
- **Worker** 池化 → 同类任务可并发、可替换
- **Reflector** 形成**单步反馈环**，避免"全做完才发现错了"
- **Supervisor** 持有全局状态，但只读 → 写竞争最小化

### 多级调度：上下文纯洁性

当 Supervisor 自己重试失败会污染上下文时，引入**总调度者（meta-supervisor）**：

```
总调度者（meta）
   ↓ 任务定义 / 进度信号
Supervisor（拆任务 / 派发）
   ↓ 派发指令
Sub-agent（执行）
   ↑ 仅回报：成功/失败 + 摘要 + 资源消耗
   ↑ 进度摘要（不含原始 trace）
总调度者（决策：升级到人？调整预算？终止？）
```

**核心原则**：**信息流的有损压缩边界** —— 执行细节只向上传播 1 层摘要，原始 trace 在子 agent session 内被 GC。

### 四个隐含但必须显式化的约束

| 约束 | 目的 |
|---|---|
| 预算意识 | 总调度者持有全局预算（token、时间、调用次数、错误率） |
| 升级路径 | Supervisor 重试 3 次失败 → 升级到总调度者，不是无限重试 |
| 失败预算 | 单个任务失败次数超过预算 → 触发更高级别干预 |
| 退出条件 | 任何循环必须有明确的退出信号 |

---

## 六、从静态库到自演化

### 核心论断

任何"agent 库 + pattern 库"无论设计多完善都不可能完备 —— **人类认知局限 + 不可预见的未来问题 = 必然不完备**。

所以 agent 库和 pattern 库**必须能演化**，方式与生物进化同构：

```
变异（agent 创造） → 选择（trace 数据反馈） → 适者生存 → 涌现秩序
```

### 与现有 AI 系统的对偶

| 系统 | 训练目标 | 数据 | 不规定什么 |
|---|---|---|---|
| GPT 预训练 | 预测下一个 token | 互联网文本 | 具体能完成什么任务 |
| AlphaZero | 赢棋 | 自己和自己下 | 棋谱、开局、残局 |
| AutoML-Zero | 验证集准确率 | 随机生成 + 搜索 | 具体模型架构 |
| Voyager | 完成 Minecraft 任务 | LLM 自己出题 | 具体技能实现 |
| Darwin-Gödel | 提升自身能力 | 自我修改尝试 | 具体改进路径 |
| **本系统** | 解题成功 + 复用率 | AI 自己出题 + 自己解 | 具体 agent/pattern 长什么样 |

**形式完全一致**：规定训练方式 + 数据流 + 反馈信号 → 不规定中间产物长什么样。

### 反直觉的根本

> **强先验 = 强天花板；弱先验 = 让数据/反馈说话。**

---

## 七、库演化协议

### 五步闭环

```
┌──────────────────────────────────────────────┐
│  1. 观察器（Observer）                       │
│     收集：用户问题、失败 trace、未解诉求    │
│     输出：{ problem_class, frequency, gap } │
└──────────────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────────────┐
│  2. 差距分析器（Gap Analyzer）               │
│     问题：这个 problem_class 是否被现有     │
│     agent 充分覆盖？                         │
│     输出：{ existing_match: 0.0~1.0,        │
│             reason_for_gap: "..." }         │
└──────────────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────────────┐
│  3. 设计器（Designer）                       │
│     仅当 gap > 阈值才触发                    │
│     按 schema 生成新 agent / pattern 草案   │
└──────────────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────────────┐
│  4. 验证门（Validation Gate）                │
│     - 相似度检查（防垃圾同质化）            │
│     - 干跑历史 trace（防无效）              │
│     - 红队测试（防脆弱）                    │
└──────────────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────────────┐
│  5. 生命周期管理（Lifecycle）                │
│     试用 → 推广 → 弃用 → GC                │
└──────────────────────────────────────────────┘
```

### 核心机制：Agent Schema

```yaml
# 新 agent 的最小结构
id: string                    # 必填，全局唯一
version: semver               # 必填，从 0.1.0 开始
role: string                  # 一句话：做什么
capabilities:                 # 必填，能力标签
  - string                    # 必须是动作短语，不是形容词
cognitive_style: enum         # 必填
  - deductive | inductive | abductive 
  - analogical | adversarial | integrative
tools_access: [string]        # 工具白名单
inputs:                       # 必填，类型化
  schema_ref: string
outputs:
  schema_ref: string
failure_modes:                # 必填，至少 2 条
  - condition: string
    recovery: string
cost_estimate:                # 必填
  tokens_per_call: int
  latency_p50: seconds
differentiation_from:         # 必填，防垃圾的核心
  - agent_id: string
    differs_in: [dimensions]  # 必须明确列出 ≥2 个不同维度
provenance:
  created_by: string
  created_at: timestamp
  reason: string              # 引用具体 gap analysis
validation:
  dry_run_traces: [string]
  adversarial_cases: [string]
  promotion_status: enum      # quarantine | beta | stable | deprecated
```

### 防垃圾协议的具体规则

| 规则 | 目的 | 例子 |
|---|---|---|
| **差异化门槛** | 防同质化 | 新 agent 必须与最相似的现有 agent 在 ≥2 个维度上不同 |
| **能力动词化** | 防抽象空话 | `capabilities` 必须是动作短语 `[critique, generate_alternative]`，不能是 `[smart, helpful]` |
| **失败模式强制声明** | 防自我吹嘘 | 必须诚实列出"什么情况下我会失败" |
| **干跑历史 trace** | 防纸上谈兵 | 必须用历史真实问题试跑并贴出对比 |
| **隔离期** | 防仓促上线 | `quarantine` 状态 7 天，期间仅实验性使用 |
| **退出机制** | 防堆积 | 30 天无调用自动进 `deprecated`，90 天自动 GC |
| **变更必须留痕** | 可审计 | 任何修改必须说明"为什么改"和"如何兼容旧调用" |

### LLM 怎么"查询"

```
角色：Library Router
任务：根据用户问题，找出最匹配的 agent + pattern 组合

输入：
- 用户问题描述
- 当前已有上下文

输出（必须严格按 schema）：
{
  "problem_class": "...",          // LLM 自己的分类
  "candidate_agents": [
    {"agent_id": "...", "match_score": 0.0~1.0, "reason": "..."}
  ],
  "candidate_patterns": [...],
  "gap_detected": bool,            // 是否需要新能力
  "if_gap": {...}                  // gap 的结构化描述
}

约束：
- match_score 必须有理由，不能凭感觉
- gap_detected 为 true 时，必须先证明现有 agent 都不够用
```

### LLM 怎么"创建"

```
角色：Library Designer
任务：基于已确认的 gap，生成新 agent 草案

前置：必须收到结构化的 gap 描述

输出：严格按上述 agent schema
      额外必须：
        - differentiation_from 列出 ≥2 个不同维度
        - failure_modes ≥2 条
        - dry_run_traces 至少 1 条

约束：
- 如果发现新 agent 与现有某个相似度 > 0.85，必须改写而不是新增
- capabilities 不能与现有任何 agent 的 capabilities 高度重叠
```

---

## 八、三层评估系统

**目标**：在合适的组织下，各 agent 充分发挥，各司其职，产出优秀的结果。

### 8.1 组织评估：组织得对不对

核心问题：这次组团方式是否让总成本最低且效果最好？

| 指标 | 含义 | 怎么算 |
|---|---|---|
| **效费比** | 单位 token 换来的结果质量 | outcome_score / total_tokens |
| **协调税** | 用于协调（消息传递、等待、汇报）的 token 占比 | coordination_tokens / total_tokens |
| **瓶颈时延** | 关键路径上最慢的 agent | max(agent_latency) over critical path |
| **重规划次数** | 中途推倒重来的次数 | count(re-plan events) |
| **空转率** | 被调用但产出未被使用的比例 | unused_outputs / total_outputs |
| **模式匹配度** | 选用的 pattern 是否事后被判合适 | 反事实估计 |

#### 反事实估计方法

| 方法 | 代价 | 可靠性 |
|---|---|---|
| 离线回放：用历史 trace 假设换 pattern 重跑 | 高 | 高 |
| LLM 自我反问："如果不用 supervisor 改用 blackboard，会更好吗？" | 低 | 中 |
| 影子模式：同时用新旧两种组织跑同一问题 | 双倍 token | 高 |
| 抽样 A/B：1% 流量用随机 pattern 探路 | 部分浪费 | 高 |

### 8.2 Agent 评估：个体好不好

**单一指标一定被 hack**，所以必须是多目标联合评估：

| 维度 | 指标 | 防止的 hack |
|---|---|---|
| **价值** | 反事实贡献：移除该 agent 后成功率下降多少 | 万能 agent（什么都能做但什么都不精） |
| **专精** | 能力标签熵低：在明确场景下被调用 | "啥都会"的低分化 agent |
| **效率** | 单位成功所需 token | 输出冗长但正确 |
| **可靠** | 同输入多次调用结果一致 | 随机性高、复现差 |
| **可独立** | 单独跑（不靠上下文）也能完成基础任务 | 必须依附特定前置 agent |
| **不过载** | 单次任务失败率（与任务难度分离后） | 故意挑软柿子 |

#### 反事实贡献的具体算法

```
baseline_success_rate: 不带这个 agent 的平均成功率（从历史估计）
with_agent_success_rate: 带这个 agent 时的成功率
counterfactual_value = with_agent_success_rate - baseline_success_rate

防止作弊：baseline 必须用同问题类型、同时间窗的对照数据
```

### 8.3 结果综合评估：产出优不优

#### A. 有客观标准的任务（代码、数学题、API 调用）

```
objective_score = {
  测试通过率,           # 最硬的信号
  性能指标达标率,       
  边界条件覆盖率,
  反例测试通过率,        # 故意构造的反例
}
```

#### B. 无客观标准的任务（写作、规划、创意）

```
                    最终产出
                       │
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
   自一致性检查    对抗性审查      分解验证
   多次跑一致吗？  找得到漏洞吗？  拆成子断言各验？
        │              │              │
        └──────────────┴──────────────┘
                       ↓
                  综合得分（加权）
```

| 验证层 | 怎么做 | 防什么 hack |
|---|---|---|
| **自一致性** | 同问题跑 3 次，关键结论一致性 | 一次碰巧答对 |
| **对抗性审查** | 让"魔鬼代言人"专门找漏洞 | 表面光鲜但脆弱 |
| **分解验证** | 拆成 N 个子断言，对每个子断言单独判 | 整体合理但细节错 |
| **外部证据** | 让 agent 引用源，下次检查源真实 | 编造数据/引用 |

#### C. 长期信号

短期指标都是代理，**真正的目标是用户长期满意**：

- **回访率**：用户下次还用这个系统的概率
- **升级率**：多少任务最终用户接管/修改
- **抱怨率**：用户明确表达不满的比例
- **替代率**：用户绕过系统自己干的比例

### 8.4 指标张力：必须显式承认

```
高复用率 ←──────────→ 高专精度
（鼓励万能 agent）    （鼓励小而专）

高效率 ←──────────→ 高鲁棒性
（鼓励走捷径）       （鼓励多重验证）

短期成功率 ←──────────→ 长期用户价值
（鼓励冒险成功）      （鼓励稳妥有用）
```

> **多目标不是缺陷，是特性**。单一目标会被 hack 到荒谬（参照 YouTube 早期只看点击率导致标题党泛滥）。指标必须互相牵制。

### 8.5 起步指标集（第一周跑这个）

```yaml
organization_metrics:
  - cost_efficiency: outcome_score / total_tokens
  - replan_count: 0 ~ small

agent_metrics:
  - reuse_rate: calls_per_day (粗指标先看趋势)
  - success_rate_when_called: success / total_calls

outcome_metrics:
  - objective_pass_rate: 自动可测的任务（代码/数学）
  - adversarial_findings: 0 ~ few (让人或 LLM 找漏洞)
  - user_satisfaction_proxy: 任务完成后用户是否继续 (二元)
```

**跑一周，看 trace，找问题，再加指标**。

---

## 九、元验证：评估系统的评估

### 核心困境

加评估系统 → 系统更复杂 → 谁验证评估系统是否正确？这是经典的元递归问题。

### 处理原则

> **不存在完全自证的评估系统。目标不是"评估系统绝对正确"，而是"失效模式已知、可见、可修复，且比没有评估时更好"。**

### 分三层验证（从廉到贵）

```
┌──────────────────────────────────────┐
│  L1. 廉价自动检查（每轮运行）         │  ← 防止系统崩溃
│     异常检测、单调性检查、自相矛盾    │
├──────────────────────────────────────┤
│  L2. 校准测试（每周跑一次）           │  ← 防止指标漂移
│     注入已知样本，看打分是否符合预期  │
├──────────────────────────────────────┤
│  L3. 人类抽查（每月一次）             │  ← 防止系统性盲区
│     抽样让人看，验证指标没骗你        │
└──────────────────────────────────────┘
```

### L1：廉价自动检查（立刻加）

| 检查 | 规则 | 触发条件 |
|---|---|---|
| **指标单调性** | 成功率不该在没改任何东西时大跳 | 周环比 ±20% 报警 |
| **调用-产出对齐** | 被调用的 agent 都应有产出 | 调用但无产出 > 5% 报警 |
| **token 爆炸** | 单次任务总 token 不该超阈值 | 超过 95 分位数报警 |
| **死循环检测** | 同 agent 重复调用不收敛 | 同 pattern 重试 > 3 次升级 |
| **指标空转** | 所有指标长期不变 → 系统可能没在学 | 7 天无变化提醒 |
| **反事实一致性** | 反事实贡献为负的 agent 不该保留 | 自动标记 deprecated |

### L2：校准测试（每周跑一次）

**核心思路：故意注入已知样本，看指标打分是否符合预期**。

```yaml
# test_set.yaml —— 每周跑一次
known_good_cases:
  - problem: "简单代码任务"
    expected_pattern: "single_agent"
    expected_success: true
    # 如果指标给分低 → 指标错
    
  - problem: "复杂多步骤研究"
    expected_pattern: "supervisor_subagent"
    expected_success: true
    # 如果指标说单 agent 更好 → 指标错

known_bad_cases:
  - problem: "模糊无解问题"
    expected_outcome: "should_admit_uncertainty"
    # 如果指标给高分 → 指标错（奖励了幻觉）

known_traps:
  - problem: "看起来简单实际复杂"
    expected_failure_mode: "early_commitment"
    # 如果指标没识别出来 → 指标错
```

**额外的高级做法：对抗性校准** —— 让独立 LLM 专门生成应该让评估系统为难的样本。

### L3：人类抽查（每月一次）

```
1. 随机抽 20 个 trace
2. 让人独立评分：
   - 组织方式合理吗？
   - Agent 真的有用吗？
   - 产出真的好吗？
3. 算与指标分的一致率（Kappa 系数）
4. 不一致的案例 → 分析指标哪里错了
```

**Kappa 系数判读**：
- > 0.8：指标和人基本一致 → 放心
- 0.5 ~ 0.8：方向对，细节偏 → 微调
- < 0.5：指标系统性骗你 → 大改

### 复杂度管理

```
Week 1:  L1 异常检测（5 条规则，几十行代码）
Week 2:  看 L1 是否触发，分析误报
Week 3:  加 L2 测试集（10 个 case）
Week 4:  看 L2 不一致比例
Month 2: 加 L3 人审（每月 1 小时）
```

**复杂度是逐步加入的，不是上来就全套**。

### 评估系统本身也要演化

> 评估系统的失败 trace 本身应该被记录，然后用同样的方法去演化它。

最终结构是四层反馈：

```
主系统（agent/pattern 演化）
    ↑
评估子系统（看主系统）
    ↑
元评估（看评估子系统）
    ↑
人的定期锚定（看元评估）
```

四层，没有终点，每一层都比上一层更稳定。

---

## 十、最小可行循环

### 整体架构图

```
   ┌────────────────────────────────────────────────────────┐
   │              User Problem                              │
   └────────────────────────────────────────────────────────┘
                          ↓
   ┌────────────────────────────────────────────────────────┐
   │   Router LLM  (Library Router 角色)                   │
   │   - 输入：问题 + 上下文                                │
   │   - 输出：problem_class + candidates + gap_detected    │
   └────────────────────────────────────────────────────────┘
                          ↓
   ┌────────────────────────────────────────────────────────┐
   │   Executor (按选定 pattern 实例化)                    │
   │   - Blackboard / Supervisor-Sub / Pipeline / Handoff  │
   │   - Agent Pool 实例化                                  │
   └────────────────────────────────────────────────────────┘
                          ↓
   ┌────────────────────────────────────────────────────────┐
   │   Outcome + Trace Logger                              │
   │   - 记录每个 agent 的 input/output                     │
   │   - 记录每个 pattern 的 metrics                       │
   │   - 记录 outcome 的 score                             │
   └────────────────────────────────────────────────────────┘
                          ↓
   ┌────────────────────────────────────────────────────────┐
   │   Evaluator (L1 + L2 + 反馈聚合)                      │
   │   - 更新 agent_metrics / pattern_metrics              │
   │   - 检测异常                                           │
   │   - 触发 gap analysis                                │
   └────────────────────────────────────────────────────────┘
                          ↓
   ┌────────────────────────────────────────────────────────┐
   │   Library Evolution (异步)                            │
   │   - Designer (生成新 agent 草案)                      │
   │   - Validation Gate (防垃圾)                          │
   │   - Lifecycle (merge / retire / GC)                   │
   └────────────────────────────────────────────────────────┘
```

### 五阶段循环伪代码

```python
def main_loop():
    while True:
        # 阶段 1: 路由
        user_problem = receive_problem()
        routing = router_llm(user_problem, current_library)
        if routing.gap_detected and routing.gap.severity > threshold:
            trigger_library_evolution(routing.gap)
        
        # 阶段 2: 执行
        result = execute_pattern(routing.selected_pattern, routing.selected_agents)
        
        # 阶段 3: 评估
        outcome_score = evaluate_outcome(result, user_problem)
        trace = collect_trace(result)
        log(user_problem, routing, result, outcome_score, trace)
        
        # 阶段 4: 反馈聚合（在线）
        update_agent_metrics(routing.selected_agents, outcome_score)
        update_pattern_metrics(routing.selected_pattern, outcome_score)
        l1_anomaly_check()  # 单调性 / token / 死循环
        
        # 阶段 5: 库演化（异步 / 周期）
        if cycle % CONSOLIDATION_INTERVAL == 0:
            consolidate_library()

def consolidate_library():
    logs = read_recent_logs()
    features = extract_features(logs)
    clusters = cluster(logs, features, by='outcome')
    rules = mine_rules(clusters)
    update_recommender(rules)
    
    # GC 低价值 agent
    retire_low_use_agents()
    
    # 合并相似 agent
    merge_similar_agents()
    
    # 升级 quarantine → beta → stable
    promote_quarantine_if_good()
```

### 反事实贡献计算（关键）

```python
def counterfactual_value(agent_id, recent_logs):
    """估算移除该 agent 后的成功率下降"""
    
    # 找到该 agent 参与的所有任务
    with_agent_logs = [log for log in recent_logs if agent_id in log.agents]
    
    # 找同问题类型但不含该 agent 的对照
    control_logs = [
        log for log in recent_logs 
        if agent_id not in log.agents 
        and log.problem_class in [l.problem_class for l in with_agent_logs]
    ]
    
    if not with_agent_logs or not control_logs:
        return 0.0  # 数据不足
    
    success_with = sum(1 for l in with_agent_logs if l.outcome.success)
    rate_with = success_with / len(with_agent_logs)
    
    success_control = sum(1 for l in control_logs if l.outcome.success)
    rate_control = success_control / len(control_logs)
    
    return rate_with - rate_control
```

---

## 附录：代码骨架

### A. Agent 定义 Schema（Python 范例）

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

class CognitiveStyle(str, Enum):
    DEDUCTIVE = "deductive"
    INDUCTIVE = "inductive"
    ABDUCTIVE = "abductive"
    ANALOGICAL = "analogical"
    ADVERSARIAL = "adversarial"
    INTEGRATIVE = "integrative"

class PromotionStatus(str, Enum):
    QUARANTINE = "quarantine"
    BETA = "beta"
    STABLE = "stable"
    DEPRECATED = "deprecated"

@dataclass
class CapabilityTag:
    """能力标签：必须是动作短语"""
    action: str              # e.g., "critique", "generate_alternative"
    domain: Optional[str]    # e.g., "code", "math"

@dataclass
class FailureMode:
    condition: str           # 在什么情况下会失败
    recovery: str            # 如何恢复 / 谁负责

@dataclass
class DifferentiationNote:
    agent_id: str
    differs_in: List[str]    # 不同维度的列表

@dataclass
class Agent:
    id: str
    version: str             # semver, e.g., "0.1.0"
    role: str                # 一句话描述
    capabilities: List[CapabilityTag]
    cognitive_style: CognitiveStyle
    tools_access: List[str]
    failure_modes: List[FailureMode]
    cost_estimate: Dict[str, float]    # tokens_per_call, latency_p50
    differentiation_from: List[DifferentiationNote]
    promotion_status: PromotionStatus = PromotionStatus.QUARANTINE
    
    def is_valid(self) -> List[str]:
        """返回所有校验失败的字段名"""
        errors = []
        if not self.role or len(self.role) > 100:
            errors.append("role 必须是非空短句")
        if not self.capabilities:
            errors.append("capabilities 不能为空")
        if any(not c.action for c in self.capabilities):
            errors.append("capability.action 不能为空")
        if not self.failure_modes or len(self.failure_modes) < 2:
            errors.append("failure_modes 至少 2 条")
        if not self.differentiation_from:
            errors.append("differentiation_from 必填（防同质化）")
        return errors
```

### B. Library Router 提示词模板

```python
LIBRARY_ROUTER_PROMPT = """
你是 Library Router。根据用户问题，从现有 agent/pattern 库中找出最匹配组合。

【输入】
- 用户问题：{problem}
- 当前上下文：{context}
- 现有 agent 库摘要：{agent_library_summary}
- 现有 pattern 库摘要：{pattern_library_summary}

【输出】严格按以下 schema：
{{
  "problem_class": "...",          // 你对问题类型的判断
  "candidate_agents": [
    {{"agent_id": "...", "match_score": 0.0~1.0, "reason": "..."}}
  ],
  "candidate_patterns": [
    {{"pattern_id": "...", "match_score": 0.0~1.0, "reason": "..."}}
  ],
  "selected_combination": {{
    "pattern_id": "...",
    "agent_ids": ["...", "..."]
  }},
  "gap_detected": false,            // 是否需要新能力
  "if_gap": null                    // 如果 gap_detected=true，填此项
}}

【约束】
- match_score 必须有 reason，不能凭感觉
- gap_detected 为 true 时，必须先证明现有所有 candidate 的 match_score < 0.6
- if_gap 必须含: existing_match_scores, reason_for_gap, suggested_capability

【禁止】
- 不要凭空发明不存在的 agent/pattern
- 不要让 selected_combination 含被标 deprecated 的 agent
"""
```

### C. Library Designer 提示词模板

```python
LIBRARY_DESIGNER_PROMPT = """
你是 Library Designer。基于已确认的 gap，生成新 agent 草案。

【输入】
- Gap 描述：{gap_description}
- 现有最相似的 agent（最多 3 个）：{similar_agents}
- 现有 capability 标签全集：{all_capability_tags}

【输出】严格按 Agent Schema：
{{
  "id": "...",
  "version": "0.1.0",
  "role": "...",
  "capabilities": [{{"action": "...", "domain": "..."}}],
  "cognitive_style": "...",
  "tools_access": ["..."],
  "failure_modes": [
    {{"condition": "...", "recovery": "..."}}
  ],
  "cost_estimate": {{"tokens_per_call": 1000, "latency_p50": 3.0}},
  "differentiation_from": [
    {{"agent_id": "...", "differs_in": ["..."]}}
  ],
  "provenance": {{
    "created_by": "library_designer",
    "reason": "...",     // 引用具体 gap
    "validation_examples": ["..."]   // 至少 1 个
  }}
}}

【强制约束】
- capabilities.action 不能与 all_capability_tags 中任何 action 高度相似
- differentiation_from 必须列出至少 2 个不同维度（如：认知风格、工具集、立场预设）
- failure_modes 至少 2 条，且 recovery 字段必须填
- 与现有任一 agent 的相似度 > 0.85 时，必须改写而不是新增

【禁止】
- 不要创建"万能 agent"（capabilities 列表 ≥ 10 个）
- 不要让 capabilities 含抽象形容词（smart、helpful 等）
"""
```

### D. 评估指标收集器

```python
@dataclass
class Trace:
    """单次任务执行完整记录"""
    timestamp: float
    user_problem: str
    problem_class: str
    selected_pattern: str
    selected_agents: List[str]
    agent_calls: List[Dict]            # 每个 agent 的 input/output/cost
    pattern_metrics: Dict              # pattern 维度的 metrics
    outcome_success: bool
    outcome_score: float               # 0.0 ~ 1.0
    objective_metrics: Optional[Dict]  # 如果可自动测
    tokens_used: int
    total_latency: float
    replan_count: int
    user_continued: Optional[bool]     # 任务完成后用户是否继续

class MetricsCollector:
    def __init__(self):
        self.traces: List[Trace] = []
    
    def record(self, trace: Trace):
        self.traces.append(trace)
        self._l1_check(trace)
    
    def _l1_check(self, trace: Trace):
        """L1 廉价自动检查"""
        # token 爆炸
        if trace.tokens_used > self.token_p95():
            alert("token_explosion", trace)
        # 死循环
        if trace.replan_count > 3:
            alert("replan_exceeded", trace)
        # 调用-产出对齐
        for call in trace.agent_calls:
            if not call.get("output"):
                alert("empty_agent_output", trace, call)
    
    def compute_agent_metrics(self, agent_id: str, window: int = 100) -> Dict:
        """计算指定 agent 的所有指标"""
        recent = self.traces[-window:]
        agent_traces = [t for t in recent if agent_id in t.selected_agents]
        control = [t for t in recent 
                   if agent_id not in t.selected_agents 
                   and t.problem_class in {x.problem_class for x in agent_traces}]
        
        if not agent_traces:
            return {"error": "insufficient_data"}
        
        reuse_rate = len(agent_traces) / max(len(recent), 1)
        success_rate = sum(1 for t in agent_traces if t.outcome_success) / len(agent_traces)
        
        cf_value = self._counterfactual_value(agent_traces, control)
        
        return {
            "reuse_rate": reuse_rate,
            "success_rate": success_rate,
            "counterfactual_value": cf_value,
            "sample_size": len(agent_traces)
        }
    
    def _counterfactual_value(self, agent_traces, control_traces) -> float:
        if not control_traces:
            return 0.0
        rate_with = sum(1 for t in agent_traces if t.outcome_success) / len(agent_traces)
        rate_control = sum(1 for t in control_traces if t.outcome_success) / len(control_traces)
        return rate_with - rate_control
```

### E. 库演化调度器

```python
class LibraryEvolutionScheduler:
    def __init__(self, library: AgentLibrary, metrics: MetricsCollector):
        self.library = library
        self.metrics = metrics
        self.consolidation_interval = 100  # 每 100 次执行做一次库整合
    
    def consolidate(self):
        """库整合周期任务"""
        # 1. GC 低价值 agent
        self._retire_low_value()
        # 2. 合并相似 agent
        self._merge_similar()
        # 3. 升级 quarantine → beta → stable
        self._promote_quarantine()
        # 4. 检测 gap（如果有 Designer）
        # self._detect_gaps_and_propose()
    
    def _retire_low_value(self):
        """反事实贡献 < 阈值 且 调用次数 < 阈值 → deprecated"""
        for agent in self.library.all_active():
            m = self.metrics.compute_agent_metrics(agent.id)
            if (m.get("counterfactual_value", 0) < -0.05 
                and m.get("reuse_rate", 0) < 0.01):
                agent.promotion_status = PromotionStatus.DEPRECATED
    
    def _merge_similar(self):
        """相似度 > 0.85 的 agent 合并"""
        all_agents = self.library.all_active()
        for i, a in enumerate(all_agents):
            for b in all_agents[i+1:]:
                sim = self._similarity(a, b)
                if sim > 0.85:
                    # 选择保留价值更高的
                    va = self.metrics.compute_agent_metrics(a.id).get("counterfactual_value", 0)
                    vb = self.metrics.compute_agent_metrics(b.id).get("counterfactual_value", 0)
                    if va > vb:
                        b.promotion_status = PromotionStatus.DEPRECATED
                    else:
                        a.promotion_status = PromotionStatus.DEPRECATED
    
    def _promote_quarantine(self):
        """quarantine agent 评估后可升级"""
        for agent in self.library.all_with_status(PromotionStatus.QUARANTINE):
            if agent.age_days() < 7:
                continue  # 隔离期未到
            m = self.metrics.compute_agent_metrics(agent.id)
            if m.get("counterfactual_value", 0) > 0.1:
                agent.promotion_status = PromotionStatus.BETA
            elif m.get("counterfactual_value", 0) < 0:
                agent.promotion_status = PromotionStatus.DEPRECATED
```

### F. 启动配置

```python
# 最小启动器
def bootstrap():
    library = AgentLibrary(seed_agents=[
        # 5-10 个种子 agent
        Agent(id="supervisor_v1", role="调度并拆解任务", ...),
        Agent(id="executor_v1", role="执行具体步骤", ...),
        Agent(id="critic_v1", role="批判性审查产出", ...),
        Agent(id="reflector_v1", role="反思并决定下一步", ...),
        Agent(id="devil_advocate_v1", role="强制反方立场", ...),
    ])
    
    patterns = PatternLibrary(seed_patterns=[
        Pattern(id="single_agent", ...),
        Pattern(id="supervisor_sub", ...),
        Pattern(id="blackboard", ...),
    ])
    
    metrics = MetricsCollector()
    evolution = LibraryEvolutionScheduler(library, metrics)
    
    # 主循环
    cycle = 0
    while True:
        trace = main_loop(library, patterns)
        metrics.record(trace)
        cycle += 1
        if cycle % evolution.consolidation_interval == 0:
            evolution.consolidate()
            print(f"[Cycle {cycle}] Library consolidated")
```

---

## 参考文献与真实先例

### 学术与工程先例

| 系统 | 启示 |
|---|---|
| **GPT 预训练** | 不规定具体任务，让 next-token 目标涌现能力 |
| **AlphaZero** | 自博弈生成训练数据，无需人类棋谱 |
| **AutoML-Zero** | 不规定模型架构，让搜索 + 验证集决定 |
| **Voyager (NVIDIA)** | Minecraft 中 LLM 终身学习，技能库持续增长 |
| **Darwin-Gödel Machine** | AI 系统递归自我改进 |
| **HuggingGPT / JARVIS** | LLM 当调度器，从模型库中选组合 |
| **AutoGen (Microsoft)** | 灵活对话模式作为一等公民 |
| **Constitutional AI (Anthropic)** | 用原则而非规则引导行为演化 |

### 哲学与认知先例

| 来源 | 启示 |
|---|---|
| **休谟《人类理解研究》(1748)** | 归纳问题：没有先验的正确分类法 |
| **Harnad 符号接地 (1990)** | 符号如何获得意义 —— 必须有外部锚点 |
| **Goodhart 定律** | 任何被优化的指标都会失效 |
| **MAPE-K 自主计算** | 多层反馈架构的工程范式 |
| **生态位理论 (Hutchinson)** | 物种不需要"中央设计"，靠信号 + 选择涌现 |

### 系统生态先例

| 系统 | 启示 |
|---|---|
| **Linux Kernel Module** | 严格的注册 + 版本 + 退出机制 |
| **npm/PyPI** | 软件包的发现、安装、淘汰生态 |
| **HuggingFace Model Cards** | 结构化模型描述 |
| **SBOM** | 软件物料清单 —— 任何"组件库"都需要可审计 |

---

## 行动指南：你的下一步

### 第一周（不动手实现，只动手观察）

1. 跑现有系统（或手工模拟 5-10 个任务），记录 trace
2. 识别"哪些场景重复出现 / 哪些能力反复缺失"
3. 列出 5-10 个种子 agent 候选

### 第二周（最小循环）

1. 实现 L1 检查（5 条规则）
2. 跑起来，看 trace 哪些规则触发 / 误报
3. 根据 trace 调整 agent 库

### 第三周（开始评估）

1. 加入 agent_metrics 的 4 个核心指标
2. 开始看到反事实贡献
3. 开始 GC 第一个 deprecated agent

### 第四周（评估校准）

1. 建立 10 个 L2 测试 case
2. 跑一次 L3 人审
3. 计算 Kappa

### 持续（演化循环）

1. 每 100 次执行触发库整合
2. 每月一次 L3 人审
3. 每季度回顾整个指标体系是否还反映你的目标

---

## 文档元信息

- **设计思想**：从静态多 agent 架构到自演化 agent 生态
- **核心张力**：预设 vs 涌现；指标 vs 现实；复杂 vs 可用
- **总原则**：**没有先验的方法，只有实践后的方法**
- **哲学基础**：休谟归纳问题 + 达尔文进化论 + 工程分层反馈
