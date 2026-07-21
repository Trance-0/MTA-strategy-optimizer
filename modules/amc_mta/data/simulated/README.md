# AMC MTA 模拟数据

此目录包含三个可复现样例：

| 文件 | 用途 |
| --- | --- |
| `amc_touchpoint_events_sample.csv` | 本地路径算法概念输入，覆盖曝光、点击、曝光后点击、乱序、14 天边界、起点拒绝、多购买和 creative 对照 |
| `amc_mta_path_report_raw_sample.csv` | 从事件生成的匿名聚合五段路径，供归因读取 |
| `amazon_ads_report_sample.csv` | 同期 Amazon Ads 风格触点表现和成本；不包含未参与计算的 campaign/ad group 管理字段 |

事件样例不是 AMC 可直接导出的用户级数据。真实 AMC 应在 clean room 内执行路径处理并只导出匿名聚合结果。

AMC 事件、路径和 Amazon Ads 报告统一使用 `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` 五段粒度。CPC 成本只归 CLICK，CPM 成本只归 IMPRESSION；non-billed 互动成本为 0，平台购买和销售只归 CLICK。报告窗口为完整自然年 `2026-01-01` 至 `2026-12-31`。全年包含 520 条事件、146 个 journey、158 次 conversion 和 6,205 条 Ads 日数据：144 次形成路径、12 次二次 conversion 因无新触点不复用、2 次边界 conversion 被拒绝。144 条路径全部唯一是合成测试设计，不是真实 AMC 证据。

重新生成并校验：

```bash
python3 modules/amc_mta/scripts/regenerate_simulated_dataset.py
python3 modules/amc_mta/scripts/validate_data_alignment.py
```

两个生成器均原子写入且可确定复现。Ads 使用自然年绝对日序，因此任意子区间与全年相同日期切片一致。
