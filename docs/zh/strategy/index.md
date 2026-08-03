---
title: 策略优化模型
description: 当前预算初始化器与未来 Ad Group 收入优化模型
lang: zh-CN
---

# 策略优化模型

## 当前：预算初始化器 <span class="status-label status-verified" aria-label="Verified"></span>

`modules/mta_strategy_recommender/src/budget_recommender.py` 的公开函数 `generate_budget_recommendation()` 明确返回确定性的、**未优化**的 Ad Group 数量和预算起点。

```text
推荐 MTA 份额 + AMC 实体 Bridge → Campaign Outcome 贡献
Campaign Outcome 贡献 × Outcome 权重 → Campaign MTA 得分
候选计数 ÷ 容量规则 → 新 Ad Group 数量
Campaign 预算 ÷ 新组数量 → 每组初始预算
```

对 Campaign (c)：

$$
\text{campaign score}(c)
= \sum_o \text{outcome weight}(o)
\times \text{campaign contribution}(c,o)
$$

对 Campaign 内的新 Ad Group：

$$
\text{initial Ad Group budget}
= \text{total budget}
\times \frac{\text{campaign score}}
{\sum_c \text{campaign score}(c)}
\div \text{recommended Ad Group count}
$$

对应文件：

| 职责 | 文件 |
| --- | --- |
| 核心计算 | `src/budget_recommender.py` |
| 生成入口 | `scripts/generate_initial_budget.py` |
| 策略输入 | `data/simulated/strategy_request.json` |
| 候选池 | `data/simulated/candidate_pool.json` |
| 当前输出 | `outputs/initial_budget_recommendation.json` |
| 输出校验 | `src/hierarchy_validator.py` |

## 下一阶段：单一 Ad Group 响应模型 <span class="status-label status-recommendation" aria-label="Recommendation"></span>

第一版优化建议只使用一个可监督、可审计的响应模型，不使用多 Agent 或多个生成模型编排。模型输入应在决策时可用：

- MTA 历史贡献和可靠性；
- Campaign、Ad Product 和 Ad Group 属性；
- Keyword、SKU、Target、Audience 等候选特征；
- 历史曝光、点击、成本、购买、收入；
- 价格、毛利、库存、预算受限和 Pacing；
- 候选预算值与时间特征。

模型输出应是每个 Ad Group 在候选预算 (b) 下的预期收入：

$$
\widehat{\text{expected revenue}}(g,b)
$$

MTA 结果应作为历史先验或特征，而不是直接等同于预算响应。

## 约束优化器 <span class="status-label status-recommendation" aria-label="Recommendation"></span>

在模型产生预算—收入响应后，单独的确定性优化器求解：

$$
\max_{b_g}
\sum_g \widehat{\text{expected revenue}}(g,b_g)
$$

满足：

$$
\sum_g b_g \le \text{total campaign budget},
\qquad
\text{minimum budget}(g) \le b_g \le \text{maximum budget}(g)
$$

还应包含库存、投放资格、预算步长和业务保护规则。若业务真正目标是利润而不是收入，应把目标函数改为预期毛利，而不是混用 Revenue、ROAS（Return on Ad Spend，广告支出回报率）和销量。

## 验证标准 <span class="status-label status-recommendation" aria-label="Recommendation"></span>

- 与等分、当前 MTA Seed 和历史预算三种基线比较；
- 使用时间外验证，避免随机拆分造成未来信息泄漏；
- 检查预测校准、预算单调性、饱和和外推范围；
- MTA-SIM Ground Truth 只在训练结束后用于合成评估；
- 生产收益必须通过合规实验或 Holdout 评估，不由 MTA 份额直接证明。

关于大规模在线实验系统的实践背景，可阅读 [Online Controlled Experiments at Large Scale](/research/ab-testing/Online%20Controlled%20Experiments%20at%20Large%20Scale.pdf)。

## 参考资料

- [Online Controlled Experiments at Large Scale（PDF）](/research/ab-testing/Online%20Controlled%20Experiments%20at%20Large%20Scale.pdf)
