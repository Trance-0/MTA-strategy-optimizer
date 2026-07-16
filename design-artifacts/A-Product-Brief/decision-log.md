# Decision Log: AI驱动营销投放优化平台 PRD

Created: 2026-06-20
Updated: 2026-07-16

## Decisions

1. 采用 Fast path 生成 PRD，因为用户明确要求“根据刚刚说的生成一个 PRD”，且已有 Product Brief 与模型讨论上下文。
2. 产品定位为 AI 驱动营销投放优化平台，核心链路为 MTA 归因、ROI 分析、效果预测、预算优化、A/B 或准实验验证。
3. PRD 主文档聚焦产品能力与可测试需求；模型选择、算法边界、数据限制等细节放入 addendum.md。
4. MVP 以可演示、可解释、可验证为目标，不包含广告投放执行系统、创意制作系统、自动媒体采购和生产级实验平台。
5. 项目同时保留 campaign 聚合样例和 AMC 匿名聚合路径样例；前者用于 ROI、预测和预算模拟，后者用于当前 AMC MTA 归因演示。
6. 将跨模块模型说明放入 `docs/product/`，将 MTA 数据需求放入对应模块的 `modules/<module>/docs/`，保持 Product Brief 文件夹只承载产品定义、附录和决策记录。

## Assumptions To Confirm

1. v1 主要是 Web dashboard + AI 问答界面。
2. v1 用户为营销负责人、广告投放团队、数据分析师和业务决策者。
3. v1 可使用历史 campaign 聚合数据做预测和预算模拟，并使用 AMC 匿名聚合路径运行当前 MTA；获得更完整的用户级或 clean-room 证据后再增强稳定性和因果验证。
4. A/B 测试在 MVP 中作为实验设计与结果记录能力，不做完整广告平台级流量分配系统。

## Deferred Items

1. 与广告平台 API 的实时双向集成。
2. 自动执行预算调整。
3. 完整用户级实验平台。
4. 企业级权限、审批和审计工作流。
