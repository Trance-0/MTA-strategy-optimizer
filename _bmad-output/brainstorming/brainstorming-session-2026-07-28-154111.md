---
stepsCompleted: [1, 2]
status: superseded
inputDocuments: []
session_topic: '基于MTA触点归因，为Campaign或Campaign Group生成以整体增量ROI最大化为目标的预算与投放建议'
session_goals: '探索模型形态与合理输出粒度；推荐总预算、Campaign间分配、Ad Group数量及预算、触点投放建议和预测ROI'
selected_approach: 'progressive-flow'
techniques_used: ['What If Scenarios', 'Mind Mapping', 'Morphological Analysis', 'Decision Tree Mapping']
ideas_generated: []
context_file: ''
---

# Brainstorming Session Results

> 历史探索说明：本会话记录了早期 ROI 优化方向，已由现行
> [`MTA-Informed Strategy Initializer` 计划](../../modules/mta_strategy_recommender/docs/model-plan.md)
> 取代。当前模型以 Campaign Group 为顶层，只生成 `INITIAL_SEED`，不实现优化器。

**Facilitator:** ericson
**Date:** 2026-07-28 15:41:11

## Session Overview

**Topic:** 基于 MTA 触点归因，为 Campaign 或 Campaign Group 生成以整体增量 ROI 最大化为目标的预算与投放建议。

**Goals:** 探索合理的模型形态和建议粒度，最终覆盖总预算、Campaign 间预算分配、Ad Group 数量与预算、触点级投放建议及预测 ROI。

### Context Guidance

MTA 结果作为历史触点贡献、路径和边际效果信号使用，不直接按归因占比分配预算。优化目标需要兼顾 ROI 与业务规模，避免模型通过建议极低预算得到形式上的最高 ROI。

### Session Setup

当前尚不预设建议必须细化到何种层级。会话将比较 Campaign、Ad Group 与触点等输出粒度，并考虑实际投放约束、数据可信度和可执行性。

**Selected Approach:** Progressive Technique Flow（渐进式探索）

## Technique Selection

**Approach:** Progressive Technique Flow

**Journey Design:** 从广泛探索逐步推进至可执行的模型方案。

**Progressive Techniques:**

- **Phase 1 - Exploration:** What If Scenarios，用于挑战假设并扩展模型可能性
- **Phase 2 - Pattern Recognition:** Mind Mapping，用于识别主题、依赖和关键决策维度
- **Phase 3 - Development:** Morphological Analysis，用于组合模型部件并形成候选架构
- **Phase 4 - Action Planning:** Decision Tree Mapping，用于依据数据条件选择方案并规划 MVP

**Journey Rationale:** 当前优化目标已经明确，但模型边界、建议粒度和算法形态尚未确定。该路径先避免过早收敛，再系统组合可选部件，最终依据数据可得性和验证要求形成实施路径。

## Confirmed Business Rules

- 一个 Campaign Group 只服务一个广告平台。
- 一个 Campaign 只投放一种 Ad Product。
- 一个 Campaign 可以包含多个 Ad Group。

因此，预算优化必须在单一平台的 Campaign Group 内完成；Ad Product 是 Campaign 的固定属性，Ad Group 继承所属 Campaign 的平台与 Ad Product 边界。

## Emerging Ideas

**[Model Boundary #1]: Hierarchical Budget Optimizer**
_Concept_: 模型按照 Campaign Group → Campaign → Ad Group 的既有层级进行预算决策。Campaign Group 决定平台内总预算，Campaign 承载单一 Ad Product 的预算，Ad Group 承载更细粒度的投放资源或出价建议。
_Novelty_: 将平台和 Ad Product 视为不可跨越的业务边界，避免把不具可替代性的投放对象放入同一个扁平优化池。

**[Model Boundary #2]: Ad-Group-First Prediction**
_Concept_: 第一版以既有 Ad Group 为主预测与预算分配单位，Keyword 和 SKU 聚合为 Ad Group 特征；Campaign 预算与结果由所属 Ad Group 汇总，Campaign Group 总预算与结果再由 Campaign 汇总。若需要推荐 Group 总预算，则在多个候选总预算下重复执行 Ad Group 分配与效果预测，形成预算—ROI 前沿后再选择。
_Novelty_: 尊重现有数据的可训练粒度和文档已定义的预测链路，同时保留 Campaign、Ad Product 与平台边界，不把缺少历史反事实的新结构数量作为同一个优化问题。

**[Attribution #3]: MTA-Calibrated Bottom-Up Allocation**
_Concept_: MTA 在最细可映射触点层输出归因价值、路径角色和置信度，再聚合到 Ad Group；预算响应模型学习各 Ad Group 在不同花费下的边际增量收益，优化器据此分配预算，并向上汇总到 Campaign、Ad Product 和 Campaign Group。
_Novelty_: MTA 提供价值归属而不是直接充当预算公式，从而避免把历史平均归因占比误当成未来边际回报。

**[Strategy Design #4]: Touchpoint-to-Ad-Group Strategy Generator**
_Concept_: Campaign 数量及每个 Campaign 的 Ad Product、Ad Group 数量作为给定容量。模型从可靠 MTA 触点中生成可执行策略，把兼容且互补的触点分配给各 Ad Group，再根据每组策略的可获得流量、成本和边际收益曲线反推预算；Campaign 与 Group 预算由 Ad Group 预算向上汇总。
_Novelty_: 不要求 MTA 原始触点预先带有 Ad Group ID，而是把 Ad Group 视为承载触点策略的执行容器，由独立策略层完成触点到投放结构的设计。
