---
title: 归因模型总览
description: MTA 组件、目标、文件和输出关系
lang: zh-CN
---

# 归因模型总览

## 归因层解决什么问题 <span class="status-label status-verified" aria-label="Verified"></span>

归因层读取历史聚合路径，回答：在当前观察窗口内，每个五段触点在转化用户、购买次数和收入中应获得多少历史信用？

输出粒度是：

```text
touchpoint × outcome → attribution share
```

它不回答“多投一美元会增加多少收入”，也不证明广告带来的因果增量。

如需了解客户旅程的重建与解释背景，可阅读 [Mapping the Customer Journey](/research/mta/Mapping%20the%20customer%20journey.pdf)；如需比较更广泛的数据驱动归因方法，可阅读 [Data-driven Multi-touch Attribution Models](/research/mta/Data-driven%20Multi-touch%20Attribution%20Models.pdf)。

## 组件、文件和目标 <span class="status-label status-verified" aria-label="Verified"></span>

| 组件 | 主要文件 | 目标 |
| --- | --- | --- |
| 路径与 Schema 校验 | `src/amc_mta_attribution.py` | 读取聚合路径，校验数量、金额和五段键 |
| Markov 归因 | `WeightedMarkovAttribution` | 用移除触点前后的转化概率差计算贡献份额 |
| Shapley 归因 | `AggregatedShapleyAttribution` | 在每条路径内部对唯一触点公平分摊 Outcome，再跨路径汇总 |
| 模型比较 | `src/model_comparison.py` | 检查计算有效性、数据支持度和模型一致性 |
| 流水线 | `run_pipeline.py` | 统一运行并发布经过验证的产物 |

> 正确术语是 **Shapley value** 和 **Markov chain**。Shapely 是另一个用于几何计算的 Python 库，不是本项目的归因模型。

## 三类 Outcome <span class="status-label status-verified" aria-label="Verified"></span>

- `converted_users`：去重转化用户数；
- `purchase_count`：购买或订单次数；
- `revenue`：收入或销售额。

每个 Outcome 分别归一化，所有触点份额之和为 1。三类 Outcome 不能相互相加。

## 双模型治理 <span class="status-label status-verified" aria-label="Verified"></span>

Markov 是当前正式展示口径，Shapley 是敏感性参照。系统不会简单取两者平均：

- 可靠时，推荐值使用 Markov `official_share`；
- 不可靠时，推荐值使用两个模型份额组成的升序闭区间；
- 策略模块若收到区间，当前只取中点并发出 Warning。

进一步阅读：[Markov 移除效应](./markov.md) · [Shapley 路径归因](./shapley.md)

## 参考资料

- [Mapping the Customer Journey（PDF）](/research/mta/Mapping%20the%20customer%20journey.pdf)
- [Data-driven Multi-touch Attribution Models（PDF）](/research/mta/Data-driven%20Multi-touch%20Attribution%20Models.pdf)
