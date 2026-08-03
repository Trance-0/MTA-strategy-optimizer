---
title: Amazon Ads 五段成本样例
lang: zh-CN
---

# Amazon Ads 五段成本样例

`data/simulated/amazon_ads_report_sample.csv` 是从
`synthetic_user_events_sample.csv` 逐日聚合的 Amazon Ads 风格表现和成本数据。样例窗口
为 `2026-01-01` 至 `2026-03-31`，共90天、1,530条数据。CSV第一行是字段名，
第二行是中文字段说明，读取程序会自动跳过说明行。

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

`INTERACTION_TYPE` 只能是 `IMPRESSION` 或 `CLICK`。从仓库根目录运行 `python3 -B modules/amc_mta/scripts/validate_data_alignment.py` 可校验账户、币种、窗口、五段触点集合和逐日覆盖。

该文件是 Campaign Group 范围内用于归因成本关联的五段汇总，不是 Campaign/Ad Group 管理结构样例。五段键中的 `AD_PRODUCT` 是归因观察维度；业务树仍是 `Campaign Group → Campaign → Ad Group → Keyword/SKU`，且 `ad_product` 只保存于 Campaign。层级样例见[策略模拟输入](strategy-simulated-data.md)。

## 成本与平台转化归属

- `CPC` 正成本只允许在 `CLICK` 行。
- `CPM` 正成本只允许在 `IMPRESSION` 行。
- 非计费互动行成本为 0，不复制基础广告的成本。
- 平台 `purchases`、`sales` 只归属 `CLICK` 行。

样例中的曝光、点击和成本直接聚合用户事件；平台 `purchases`、`sales` 由每个journey
最后一个符合条件的CLICK派生。Amazon Ads汇总表本身仍不用于反推AMC路径；两者只是
共享同一模拟事实源。`reported_purchases`不会替代AMC outcome口径。效率指标按同一
五段行计算；成本为0时为空。
