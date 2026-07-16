# AMC MTA 使用说明

所有命令均从项目根目录运行。字段与路径规则见[数据契约](amc-data-requirements.md)。

## 运行

完整流程：

```bash
python3 modules/amc_mta/run_pipeline.py
```

只生成聚合路径：

```bash
python3 modules/amc_mta/scripts/build_amc_path_report.py
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

```text
modules/amc_mta/outputs/attribution/amc_markov_attribution_results.csv
modules/amc_mta/outputs/attribution/amc_shapley_attribution_results.csv
modules/amc_mta/outputs/attribution/amc_mta_model_comparison_touchpoints.csv
modules/amc_mta/outputs/attribution/amc_mta_model_comparison_summary.csv
modules/amc_mta/outputs/attribution/amc_mta_recommended_attribution.csv
```

两份结果均按 `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` 五段粒度输出，包含 `interaction_type`、三套归因值、Amazon Ads 表现与成本、`roas`、`roi`、`cpa` 和 `cost_per_converted_user`。CPC 成本只出现在 CLICK 行，CPM 成本只出现在 IMPRESSION 行；非计费行的成本和效率指标为 0/空。

触点比较文件固定包含 `17 × 3 = 51` 行，逐项保存 Markov/Shapley share、
归因值、成本表现、两套效率、差距等级和从五段 AMC 路径重算的支持度。
摘要文件固定包含三个 outcome 的三行，`grain` 全部为 `FIVE_PART`；
其中 `tvd` 和 share 均以 0–1 小数保存，`gap_pp` 才是百分点。推荐文件保留
全部 51 行。稳定性证据缺失时，`official_share` 仅展示 intended Markov 口径，
所有 `decision_value` 为空且 `automation_allowed=false`。
