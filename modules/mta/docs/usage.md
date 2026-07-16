# MTA 使用说明

这份说明用于运行 Markov Chain Attribution、Shapley Value Attribution，并自动生成结果表和对比图。

## 1. 文件放在哪里

MTA 相关文件都在：

```text
modules/mta/
```

核心位置：

| 路径 | 作用 |
| --- | --- |
| `modules/mta/config.py` | 统一配置入口，只需要在这里改数据路径 |
| `modules/mta/run_pipeline.py` | 一键运行完整流程 |
| `modules/mta/src/mta_attribution.py` | Markov 和 Shapley 模型代码 |
| `modules/mta/scripts/run_mta_attribution.py` | 只生成归因结果 |
| `modules/mta/scripts/plot_mta_comparison.py` | 只生成对比图 |
| `modules/mta/data/simulated/` | 当前模拟数据 |
| `modules/mta/outputs/attribution/` | 归因结果输出 |
| `modules/mta/outputs/figures/` | 图表输出 |
| `modules/mta/docs/` | MTA 文档 |

## 2. 准备数据

你的数据文件夹需要包含三张表：

```text
markov_user_paths.csv
shapley_user_channel_sets.csv
channel_spend.csv
```

当前默认数据路径是：

```text
modules/mta/data/simulated
```

## 3. 修改数据路径

只需要改一个文件：

```text
modules/mta/config.py
```

修改这一行：

```python
DATA_DIR = MTA_ROOT / "data" / "simulated"
```

例如，如果你把新数据放在：

```text
modules/mta/data/my_company_data
```

就改成：

```python
DATA_DIR = MTA_ROOT / "data" / "my_company_data"
```

## 4. 一键运行完整流程

在项目根目录运行：

```bash
python3 modules/mta/run_pipeline.py
```

它会自动完成：

```text
读取数据
跑 Markov Chain Attribution
跑 Shapley Value Attribution
计算 ROAS / ROI / CPA
生成 CSV 结果
生成 SVG 对比图
```

## 5. 输出文件

归因结果输出到：

```text
modules/mta/outputs/attribution/
```

包括：

```text
markov_attribution_results.csv
shapley_attribution_results.csv
```

图表输出到：

```text
modules/mta/outputs/figures/
```

包括：

```text
mta_model_comparison.svg
mta_roi_comparison.svg
markov_bootstrap_boxplot.svg
shapley_bootstrap_boxplot.svg
```

## 6. 单独运行某一步

只跑归因结果：

```bash
python3 modules/mta/scripts/run_mta_attribution.py
```

只生成图：

```bash
python3 modules/mta/scripts/plot_mta_comparison.py
```

通常建议直接运行：

```bash
python3 modules/mta/run_pipeline.py
```
