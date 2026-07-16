# 模块索引

`modules/` 保存可运行的分析能力。每个模块自行管理代码、输入数据、输出、测试和使用文档。

| 模块 | 用途 | 状态 | 入口 |
| --- | --- | --- | --- |
| 通用 MTA | 使用 Markov 和 Shapley 进行多触点归因 | 已有初步实现 | [mta/README.md](mta/README.md) |
| AMC MTA | 基于 AMC 匿名聚合路径进行五段互动粒度归因和双模型评估 | 已有初步实现 | [amc_mta/README.md](amc_mta/README.md) |

## 目录约定

```text
modules/<module>/
├── data/       # 模块专用输入和样例
├── docs/       # 数据契约和使用说明
├── outputs/    # 可再生运行结果
├── scripts/    # 命令行脚本
├── src/        # 核心实现
└── tests/      # 自动化测试（若有）
```

项目级产品说明放在 [`docs/product/`](../docs/product/)，论文和外部参考资料放在 [`docs/research/`](../docs/research/)，不与模块运行输入混放。

