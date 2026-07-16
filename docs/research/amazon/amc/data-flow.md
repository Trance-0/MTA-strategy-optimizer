# AMC、MTA 与 ROI 数据流

## 两类输入

```text
AMC anonymous aggregated path report
  five-part interaction path + users + converted_users + purchase_count + revenue
                    │
                    ▼
            Markov / Shapley
                    │
                    ▼
five-part interaction attribution
                    │
                    ├── join the same five-part touchpoint
                    │
Amazon Ads performance and spend report
  impressions + clicks + cost + reported sales
                    │
                    ▼
               ROAS / ROI / CPA
```

AMC 路径回答“哪些触点组合参与了转化”；Amazon Ads 报表回答“每个触点花了多少钱”。成本通常不天然属于一条用户路径，因此应先完成归因，再在相同触点粒度关联成本。

## 当前项目口径

- AMC 风格输入是一行一类聚合路径，不是一行一个用户；模型分别按 `converted_users`、`purchase_count` 和 `revenue` 计算。
- AMC 路径与模型使用 `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` 五段键，最后一段只能是 `IMPRESSION` 或 `CLICK`。
- Amazon Ads 成本也使用完整五段键。CPC 成本只归 `CLICK`，CPM 成本只归 `IMPRESSION`，非计费互动行成本为 0；归因结果不再降回四段。
- `converted_users` 是去重购买用户数，`purchase_count` 是订单次数，两者不可互换。
- 14 天连续路径、报告窗口和模型约束见[当前数据契约](../../../../modules/amc_mta/docs/amc-data-requirements.md)。

## 指标

```text
ROAS = attributed_revenue / cost
ROI  = (attributed_revenue - cost) / cost
CPA  = cost / attributed_purchase_count
cost_per_converted_user = cost / attributed_converted_users
```

当前程序拒绝多账户、多 marketplace 或多币种混合输入；此类场景需要先按范围分区运行和关联。
