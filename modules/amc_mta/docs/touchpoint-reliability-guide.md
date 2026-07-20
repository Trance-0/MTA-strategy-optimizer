# AMC MTA 单触点归因可靠性判断

## 用途

本文用于判断一个五段触点的归因结果是否值得信任、应该如何解释。

本模型只用于归因分析，不用于预算分配或投放优化。归因结果也不代表因果增量。

五段触点格式：

```text
AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE
```

`IMPRESSION` 和 `CLICK` 是两个独立触点，必须分别判断。

## 查看顺序

1. 在 `amc_mta_model_comparison_summary.csv` 确认对应 outcome 计算有效。
2. 在 `amc_mta_recommended_attribution.csv` 查看 Markov 正式份额和 Shapley 参照份额。
3. 在 `amc_mta_model_comparison_touchpoints.csv` 判断支持度、稳定性和模型差距。

快消品 outcome 查看顺序：

```text
purchase_count → revenue → converted_users
```

## 判断步骤

### 1. 计算是否有效

检查：

```text
operational_status = VALID
validation_error_count = 0
```

如果校验失败，不解释该归因结果。

### 2. 数据支持是否充分

| 支持等级 | 购买次数 | 购买用户 | 唯一路径数 | 解释 |
| --- | ---: | ---: | ---: | --- |
| `FULL_SUPPORT` | `>= 100` | `>= 50` | `>= 10` | 支持较充分 |
| `LIMITED_SUPPORT` | `>= 30` | `>= 20` | `>= 5` | 证据有限 |
| `LOW_SUPPORT` | 任一低于 LIMITED 门槛 | 任一低于 LIMITED 门槛 | 任一低于 LIMITED 门槛 | 仅作探索性归因 |

三个条件必须同时满足。购买量很大但唯一路径很少，仍属于低支持度。

### 3. 时间是否稳定

检查：

```text
stability_level
markov_interval_low / markov_interval_high
shapley_interval_low / shapley_interval_high
gap_direction_rate
top5_entry_rate
```

如果 `stability_level=UNVERIFIED`，只能说明当前窗口的归因结果，不能表述为长期
稳定贡献。

当前项目尚未完成滚动窗口和重采样验证，因此所有结果都属于探索性归因。

### 4. 两个模型是否一致

| 等级 | 判断 | 解释方式 |
| --- | --- | --- |
| `LONG_TAIL` | 平均份额 `< 1%` | 贡献很小，避免放大相对差 |
| `SMALL` | `gap_pp <= 1` 且相对差 `<= 20%` | 两模型对贡献量级判断接近 |
| `MEDIUM` | 不属于其他等级 | 归因份额对模型假设有一定敏感性 |
| `LARGE` | `gap_pp >= 3` 或达到组合门槛 | 两模型对贡献大小存在明显分歧 |

其中：

```text
gap_pp = 100 × |markov_share - shapley_share|
```

处理方法：

- `SMALL`：以 Markov 为正式归因值，Shapley 作为参照。
- `MEDIUM`：同时展示两个模型和 `model_low ~ model_high`。
- `LARGE`：并列展示两个模型，不取平均。
- `critical_divergence=true`：优先调查路径、窗口和人群结构。

### 5. 三个 outcome 是否一致

定义：

```text
markov_outcome_spread_pp
= 100 × (Markov三个outcome最大share - 最小share)

shapley_outcome_spread_pp
= 100 × (Shapley三个outcome最大share - 最小share)

outcome_spread_pp
= max(markov_outcome_spread_pp, shapley_outcome_spread_pp)
```

| `outcome_spread_pp` | 结论 |
| ---: | --- |
| `<= 2pp` | 三个 outcome 基本一致 |
| `> 2pp` 且 `<= 5pp` | 存在一定 outcome 差异 |
| `> 5pp` | outcome 明显不一致，应分别解释 |

该指标取两个模型中较大的极差，避免只看 Markov 或只看 Shapley。如果任一 outcome
为 `NO_OUTCOME`，则不计算该指标。

## 可靠性等级

| 等级 | 条件 | 呈现方式 |
| --- | --- | --- |
| 高 | 计算有效、`FULL_SUPPORT`、稳定性通过、差距小、`outcome_spread_pp <= 2pp` | Markov 正式展示，Shapley 参照 |
| 中 | 计算有效、至少 `LIMITED_SUPPORT`、稳定性通过，但存在中等差距 | 同时展示两个模型和模型区间 |
| 低 | `LOW_SUPPORT`、稳定性未验证/不稳定、差距大或存在关键分歧 | 标记为探索性归因 |
| 无效 | 输入、守恒、窗口或字段校验失败 | 不展示归因结论 |

最终等级取最弱的一项。例如：

```text
FULL_SUPPORT + SMALL + UNVERIFIED = 低可靠
```

## 当前样例

触点：

```text
SPONSORED_PRODUCTS:PRODUCT_AD:PRODUCT_PAGE:UNSPECIFIED:CLICK
```

购买次数归因：

| 字段 | 当前值 |
| --- | ---: |
| Markov | 13.249% |
| Shapley | 19.757% |
| `gap_pp` | 6.508pp |
| `difference_level` | `LARGE` |
| `critical_divergence` | `true` |
| `raw_unique_paths` | 4 |
| `support_level` | `LOW_SUPPORT` |
| `stability_level` | `UNVERIFIED` |
| `outcome_spread_pp` | 1.633pp |

结论：

```text
归因可靠性：低
```

三个 outcome 本身基本一致，但支持度、时间稳定性和双模型差距仍未通过，所以不能
提升整体可靠性等级。

推荐表述：

> 两个模型都认为该触点是重要贡献来源，但对贡献大小存在明显分歧。由于独立路径
> 和时间稳定性证据不足，该结果只代表当前样例中的探索性归因。

## 快速检查

- [ ] 整体计算有效；
- [ ] 支持度不是 `LOW_SUPPORT`；
- [ ] 稳定性已经验证；
- [ ] 已比较 Markov 和 Shapley；
- [ ] 已查看 `gap_pp` 和 `critical_divergence`；
- [ ] 已检查三个 outcome；
- [ ] 未把归因结果解释为因果增量。
