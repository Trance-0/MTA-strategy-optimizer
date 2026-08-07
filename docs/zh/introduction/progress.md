---
title: 进展与待办
description: 已实现能力、已知限制和下一阶段优先级
lang: zh-CN
---

# 进展与待办

## 已实现 <span class="status-label status-verified" aria-label="Verified"></span>

- 聚合 AMC 风格路径的确定性处理与输入校验。
- 五段触点键：`AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`。
- Markov 与 Path-level Shapley 对 `converted_users`、`purchase_count`、`revenue` 三类 Outcome 的归因。
- 双模型比较、可靠性标记和推荐归因输出。
- 从触点归因到 Campaign 的实体 Bridge。
- 基于候选容量的新 Ad Group 数量计算。
- 基于 Campaign MTA 得分并在组内等分的初始预算。
- VitePress 中英双语导航、Cloudflare 构建和本地 PDF 服务。

## 已知限制 <span class="status-label status-verified" aria-label="Verified"></span>

- 当前策略模块是确定性的预算初始化器，`is_optimized=false`。
- 同一 Campaign 内的新 Ad Group 没有可区分的候选实体特征，因此只能等分。
- MTA 份额描述历史信用分配，不等于增加预算后的边际收入。
- MTA-SIM 的四段标准化触点与本项目的五段互动感知触点不能直接互换。
- 当前没有滚动窗口稳定性、响应曲线、离线策略评估或在线实验闭环。

## 下一阶段待办 <span class="status-label status-recommendation" aria-label="Recommendation"></span>

1. **建立数据适配层**：明确 MTA-SIM 四段键到本项目五段键的映射策略，禁止隐式猜测 `INTERACTION_TYPE`。
2. **形成 Ad Group 特征表**：加入候选 Keyword、SKU、Target、Audience、价格、毛利、库存、历史 Spend 和预算受限状态。
3. **定义单一响应模型**：预测 `expected_revenue(ad_group, budget)`，先用一个受监督模型完成可审计基线，不引入多模型代理工作流。
4. **实现约束优化器**：在总预算、最低预算、容量和业务资格约束内最大化预期收入。
5. **离线验证**：时间切分、基线对比、校准和敏感性分析；合成 Ground Truth 仅用于最终评估。
6. **上线前验证**：通过随机对照实验或合规 Holdout 评估增量效果，避免把观察性归因当作因果收益。

## 完成定义 <span class="status-label status-recommendation" aria-label="Recommendation"></span>

优化模块只有在以下条件同时满足时，才应标记为“优化”：能够预测预算变化后的结果、约束被机器校验、方案优于明确基线、结果可复算，并且输出仍标明观察性证据与因果证据的边界。
