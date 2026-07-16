# MTA Module

This folder contains all Multi-Touch Attribution work for the project: data, model code, run scripts, outputs, and documentation.

## Structure

```text
modules/mta/
├── README.md
├── config.py
├── run_pipeline.py
├── data/
│   └── simulated/
│       ├── user_touchpoint_events.csv
│       ├── markov_user_paths.csv
│       ├── shapley_user_channel_sets.csv
│       └── channel_spend.csv
├── docs/
│   ├── mta-data-requirements.md
│   └── usage.md
├── outputs/
│   ├── attribution/
│   └── figures/
├── scripts/
│   ├── plot_mta_comparison.py
│   └── run_mta_attribution.py
└── src/
    └── mta_attribution.py
```

`user_touchpoint_events.csv` 是便于追溯的事件明细样例；当前模型直接读取的派生输入是 `markov_user_paths.csv`、`shapley_user_channel_sets.csv` 和 `channel_spend.csv`。这些文件均保留在目录中，不依赖不存在的压缩包。

## Main Usage

Change the dataset path in:

```text
modules/mta/config.py
```

Then run the full pipeline from the project root:

```bash
python3 modules/mta/run_pipeline.py
```

Full instructions:

```text
modules/mta/docs/usage.md
```

## Related Project Docs

The broader model relationship guide lives outside the MTA module because it covers MTA, ROI, prediction, budget optimization, and validation together:

[Model relationship guide](../../docs/product/model-relationship-guide.md)
