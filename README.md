# Lancelot

> 元框架（meta-framework）：用来造 agent 框架的工具。

Lancelot 不是 agent 框架，是 agent 框架的"组装说明书 + 组装器"。它本身不提供 agent 能力，它让用户从一组可替换的插件（记忆、模型、工具、channel、agent 编排）中选一个组合，由 Lancelot 把它们生成成一个真正能跑的 agent 框架。

## 文档

入门请按顺序阅读：

| # | 文档 | 说明 |
|---|---|---|
| 0 | [`整体架构设计.md`](整体架构设计.md) | 整体架构（v2）。基线。所有实现必须能映射回这里。 |
| 1 | [`docs/01-V1 范围与边界.md`](docs/01-V1范围与边界.md) | V1 做什么、不做什么、成功判据。 |
| 2 | [`docs/02-Manifest 协议.md`](docs/02-Manifest协议.md) | 插件怎么描述自己。 |
| 3 | [`docs/03-端口契约.md`](docs/03-端口契约.md) | 每个端口的方法、参数、异常。 |
| 4 | [`docs/04-装配器协议.md`](docs/04-装配器协议.md) | scan / select / generate / launch 的具体协议。 |
| 5 | [`docs/05-合规性测试规范.md`](docs/05-合规性测试规范.md) | 怎么验证一个实现满足端口契约。 |
| 6 | [`docs/06-插件开发指南.md`](docs/06-插件开发指南.md) | 怎么写一个插件。 |
| 7 | [`docs/07-生成物结构.md`](docs/07-生成物结构.md) | 装配器生成出来的框架长什么样。 |

参考文档：

- [`multiagent-architecture-design.md`](multiagent-architecture-design.md) —— 后续生成物的一种 agent 框架设计提案，与 Lancelot 元框架本身解耦。

## 当前阶段

V1 文档先行阶段。代码尚未开工。详见 [`docs/01-V1范围与边界.md`](docs/01-V1范围与边界.md)。

## 仓库约定

- 默认分支：`main`
- 提交信息：祈使句、英文（或中文短句），解释"为什么"而非"做了什么"
- 不引入 worktree / 不引入 CI / 不引入远程，直到 V1 验收通过
