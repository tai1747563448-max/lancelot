# plugins/

V1 期间此目录**留空**。

Lancelot V1 不实现 plugin loader。所有用户/第三方实现按 **adapter** 走（位于 `adapters/`），必须重新装配才能换。

V2 计划：

- 引入 plugin loader（在生成物启动时按 manifest 动态加载 plugin）
- 部分 adapter（如外部服务集成类的 tools）可搬到 `plugins/`
- Manifest schema 不变，只换物理位置

详见 `docs/01-V1范围与边界.md` "术语定义"小节。