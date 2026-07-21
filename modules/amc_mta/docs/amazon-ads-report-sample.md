# Amazon Ads 五段成本样例

`modules/amc_mta/data/simulated/amazon_ads_report_sample.csv` 模拟与 AMC 路径粒度一致的 Amazon Ads 表现和成本数据。样例窗口为完整自然年 `2026-01-01` 至 `2026-12-31`，共 365 天、6,205 条数据。CSV 第一行是字段名，第二行是中文字段说明，读取程序会自动跳过说明行。

## 字段与关联键

- 范围：`reportDate`、`marketplace`、`accountId`、`currencyCode`。
- 广告维度：`adProduct`、`adType`、`creativeType`、`inventoryType`、`placement`。
- 互动与计费：`interaction_type`、`cost_type`。
- 派生关联键：`normalizedTouchpoint`。
- 表现：`impressions`、`clicks`、`cost`、`purchases`、`sales`。

`normalizedTouchpoint` 必须与程序从原始维度和 `interaction_type` 重算的键完全一致：

```text
AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE
```

`INTERACTION_TYPE` 只能是 `IMPRESSION` 或 `CLICK`。运行 `python3 modules/amc_mta/scripts/validate_data_alignment.py` 可校验账户、币种、窗口、五段触点集合和逐日覆盖。

## 成本与平台转化归属

- `CPC` 正成本只允许在 `CLICK` 行。
- `CPM` 正成本只允许在 `IMPRESSION` 行。
- 非计费互动行成本为 0，不复制基础广告的成本。
- 平台 `purchases`、`sales` 只归属 `CLICK` 行。

Amazon Ads 的汇总指标不用于生成或推断 AMC 用户路径。输出中的 `reported_purchases` 是平台报告值，不会替代 AMC 的订单口径。效率指标直接按同一五段行计算；成本为 0 时为空。
