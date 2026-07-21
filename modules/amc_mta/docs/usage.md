# AMC MTA 使用说明

所有命令均从项目根目录运行。字段与路径规则见[数据契约](amc-data-requirements.md)。
本模块只用于归因分析，不用于预算分配或投放优化。

## 运行

完整流程：

```bash
python3 -B modules/amc_mta/run_pipeline.py
```

只需替换 events 与 Amazon Ads 两份输入后再次运行。正式流程自动采用 Ads
`reportDate` 的最早日至最晚日作为窗口，无需修改 `config.py`。路径和五份模型
结果会先在临时目录全部完成并校验，再统一发布；输入错误、空路径或发布失败时，
已有六份派生产物保持不变，原始输入不会被程序覆盖。

使用自定义输入与输出位置：

```bash
python3 -B modules/amc_mta/run_pipeline.py \
  --events-file path/to/amc_touchpoint_events.csv \
  --amazon-ads-report path/to/amazon_ads_report.csv \
  --path-report path/to/amc_path_report.csv \
  --output-dir path/to/attribution_outputs
```

只生成聚合路径：

```bash
python3 -B modules/amc_mta/scripts/build_amc_path_report.py
```

该命令同样默认从 Ads 输入自动识别窗口。需要时可单独覆盖任一文件路径：

```bash
python3 -B modules/amc_mta/scripts/build_amc_path_report.py \
  --events-file path/to/amc_touchpoint_events.csv \
  --amazon-ads-report path/to/amazon_ads_report.csv \
  --output-file path/to/amc_path_report.csv
```

重新生成确定性的 Amazon Ads 模拟数据：

```bash
python3 modules/amc_mta/scripts/generate_simulated_amazon_ads_report.py
```

只对已有聚合路径运行归因：

```bash
python3 modules/amc_mta/scripts/run_amc_attribution.py
```

严格复算已有 Markov/Shapley 文件的三份比较产物：

```bash
python3 modules/amc_mta/scripts/compare_attribution_models.py
```

该命令不清洗输入；物理表头、值空白、模型名、触点集合、非有限值、负值或
share/归因值不守恒都会直接报错。

可选参数：

```bash
python3 modules/amc_mta/scripts/run_amc_attribution.py \
  --amc-report path/to/report.csv \
  --amazon-ads-report path/to/amazon_ads_report.csv \
  --output-dir path/to/output
```

校验 AMC 与 Amazon Ads 五段互动的窗口、账户、币种、触点集合及逐日覆盖：

```bash
python3 modules/amc_mta/scripts/validate_data_alignment.py
```

## 默认输入与输出

输入位于 `modules/amc_mta/data/simulated/`；文件角色见该目录的 [README](../data/simulated/README.md)。

每次运行只接受一个市场、账户和币种范围。Ads 必须非空、日期连续、每日五段触点
集合一致，且键日期组合唯一；events 必须包含转化，所有转化均在 Ads 窗口内并
至少形成一条有效路径。任何条件不满足都会直接报错，不裁剪、不补零、不发布。

```text
modules/amc_mta/outputs/attribution/amc_markov_attribution_results.csv
modules/amc_mta/outputs/attribution/amc_shapley_attribution_results.csv
modules/amc_mta/outputs/attribution/amc_mta_model_comparison_touchpoints.csv
modules/amc_mta/outputs/attribution/amc_mta_model_comparison_summary.csv
modules/amc_mta/outputs/attribution/amc_mta_recommended_attribution.csv
```

两份结果均按 `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` 五段粒度输出，包含 `interaction_type`、三套归因值、Amazon Ads 表现与成本、`roas`、`roi`、`cpa` 和 `cost_per_converted_user`。CPC 成本只出现在 CLICK 行，CPM 成本只出现在 IMPRESSION 行；非计费行的成本和效率指标为 0/空。

触点比较文件固定为 14 列、`17 × 3 = 51` 行，只保存两模型 share、`gap_pp`、
`relative_gap`、三个原始支持量和可靠性。摘要固定为 13 列、三个 outcome 三行，
保存窗口、触点数、TVD、Spearman、Top-K 重合率和可靠性。推荐文件固定为 14 列、
51 行，保存 Markov 正式展示值、Shapley 参照值、差距和可靠性。三份产物均包含
`calculation_valid`、
`data_support_sufficient`、`models_consistent`、`reliability_status` 和
`reliability_reason`；两份单模型结果不含这些字段。三个布尔值全部为 `true`
时才是 `RELIABLE`。摘要按 outcome 分别 AND 聚合全部触点的三个布尔值；
Markov 是正式归因展示口径，Shapley 用于判断模型敏感性。旧成本、效率、差距
等级和状态字段不属于这三份双模型 schema。

当前全年样例为 `51 RELIABLE / 0 UNRELIABLE`。结果只能解释为
当前窗口中的探索性归因，不能据此自动调整预算。

单个触点的归因是否可靠、应该如何解释，见
[单触点归因可靠性判断说明](touchpoint-reliability-guide.md)。
